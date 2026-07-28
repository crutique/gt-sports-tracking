"""Backfill runner for the StatBroadcast archive -- built to run for days.

Two phases, deliberately separated so the slow one is restartable and the fast
one only happens once:

``index``
    Walk the S3 listing on ``archive.statbroadcast.com`` and record every
    ``{sbid}.xml`` object with its ``LastModified`` date. ~2000 requests for the
    whole archive. The cursor is persisted after every page, so an interrupted
    index resumes where it stopped rather than starting over.

``ingest``
    Work through indexed objects in a date window, fetch each XML, and load the
    baseball ones. Every attempt is recorded in ``cbb.ingest_log`` -- including
    the ones that turn out to be softball, or missing, or malformed -- because
    the gap list is a product, not an accident.

Both phases are safe to re-run: indexing upserts, ingestion skips anything
already logged ``ok`` unless ``--redo`` is given.

Ordering note: the listing is **lexicographic**, so ``65157`` sorts between
``651569`` and ``651570``. Never infer chronology from it -- ``LastModified`` is
the only date signal, and ``sbid`` is not ordered by game date at all.

Usage on the Pi::

    .venv/bin/python -m pipeline.backfill index
    .venv/bin/python -m pipeline.backfill ingest --from 2023-01-01 --to 2026-12-31
"""
import argparse
import datetime as dt
import re
import sys
import traceback

from pipeline import statbroadcast as SB
from pipeline import statcrew
from pipeline.db import load

SOURCE = "statbroadcast_xml"


def _log(msg):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


# ------------------------------------------------------------------- index --
def _cursor(conn, name):
    with conn.cursor() as cur:
        cur.execute("SELECT cursor FROM cbb.crawl_state WHERE name = %s", (name,))
        row = cur.fetchone()
    return row[0] if row else ""


def _save_cursor(conn, name, value):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO cbb.crawl_state (name, cursor) VALUES (%s, %s) "
            "ON CONFLICT (name) DO UPDATE SET cursor = EXCLUDED.cursor, "
            "updated_at = now()", (name, value))
    conn.commit()


def run_index(conn, restart=False, max_pages=None):
    """Enumerate the archive bucket into ``cbb.archive_object``."""
    marker = "" if restart else _cursor(conn, "sb_index")
    _log(f"index: resuming from marker={marker!r}")
    seen = kept = 0
    batch = []
    for key, lastmod, size in SB.list_objects(marker=marker, max_pages=max_pages):
        seen += 1
        marker = key
        if key.endswith(".xml"):
            sbid = SB.sbid_of(key)
            if sbid:
                batch.append((int(sbid), lastmod or None, size))
                kept += 1
        if len(batch) >= 500:
            _flush(conn, batch)
            _save_cursor(conn, "sb_index", marker)
            batch = []
            _log(f"index: {seen} objects scanned, {kept} xml recorded")
    if batch:
        _flush(conn, batch)
    _save_cursor(conn, "sb_index", marker)
    _log(f"index: done -- {seen} objects scanned, {kept} xml recorded")
    return kept


def _flush(conn, rows):
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO cbb.archive_object (sbid, last_modified, xml_bytes) "
            "VALUES (%s, %s, %s) ON CONFLICT (sbid) DO UPDATE SET "
            "last_modified = EXCLUDED.last_modified, xml_bytes = EXCLUDED.xml_bytes",
            rows)
    conn.commit()


# ------------------------------------------------------------------ ingest --
def _pending(conn, date_from, date_to, redo, limit):
    """Indexed objects in the window that have not already loaded cleanly.

    Ordered newest first: the recent seasons are the ones with the best data and
    the most immediate use, so an interrupted run still leaves the useful half done.
    """
    skip = "" if redo else (
        " AND NOT EXISTS (SELECT 1 FROM cbb.ingest_log l "
        " WHERE l.source = %(src)s AND l.key = ao.sbid::text AND l.status = 'ok')")
    sql = (
        "SELECT ao.sbid, ao.last_modified FROM cbb.archive_object ao "
        "WHERE ao.last_modified BETWEEN %(f)s AND %(t)s" + skip +
        " ORDER BY ao.last_modified DESC, ao.sbid DESC")
    params = {"f": date_from, "t": date_to, "src": SOURCE}
    if limit:
        sql += " LIMIT %(lim)s"
        params["lim"] = limit
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _header(conn, sbid):
    """``(root_tag, sched_innings)`` for ``sbid``, remembered after first look.

    Classification is cached in ``cbb.archive_object`` so an object is peeked at
    most once across every re-run of the crawl.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT root_tag, sched_innings FROM cbb.archive_object "
                    "WHERE sbid = %s", (sbid,))
        row = cur.fetchone()
    if row and row[0]:
        return row[0], row[1] or 0
    tag, innings = SB.peek_header(sbid)
    with conn.cursor() as cur:
        cur.execute("UPDATE cbb.archive_object SET root_tag = %s, sched_innings = %s "
                    "WHERE sbid = %s", (tag or "?", innings, sbid))
    return (tag or "?"), innings


def ingest_one(conn, sbid):
    """Fetch, classify and load a single archived game. Returns a status string."""
    tag, innings = _header(conn, sbid)
    if tag is None or tag == "?":
        load.log_ingest(conn, SOURCE, sbid, "missing", detail="no object")
        return "missing"
    if tag != "bsgame":
        load.log_ingest(conn, SOURCE, sbid, "skipped", detail=f"root <{tag}>")
        return "skipped"
    # Reject softball from the header alone. It shares the `bsgame` root and made
    # up 36% of a season's objects, so downloading each one in full before
    # discarding it was the single largest waste in the crawl.
    if innings and innings < SB.BASEBALL_INNINGS:
        load.log_ingest(conn, SOURCE, sbid, "skipped",
                        detail=f"softball ({innings}-inning)")
        return "softball"

    xml = SB.fetch_xml(sbid)
    if xml is None:
        load.log_ingest(conn, SOURCE, sbid, "missing", detail="no object")
        return "missing"

    parsed = statcrew.parse_game(xml)
    if not SB.is_baseball(parsed):
        # only reachable when the header carried no schedinn (2 of 3000 files)
        load.log_ingest(conn, SOURCE, sbid, "skipped",
                        game_date=parsed.get("date") or None, detail="softball")
        return "softball"
    if not parsed.get("date") or not parsed.get("home") or not parsed.get("away"):
        load.log_ingest(conn, SOURCE, sbid, "error", detail="missing teams or date")
        return "error"

    # Scorers mistype the year -- real files carry 1926 for 2026, which would
    # file a game under a season a century early and quietly poison any
    # season-level aggregate. Flag rather than guess: the row lands in the gap
    # list where it can be corrected deliberately.
    # Real observed values: '1926-02-28' (year mistyped), '0206-20-26'
    # (transposed), and bare '3/1' (truncated, which reaches Postgres as an
    # invalid date and aborts the transaction).
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", parsed["date"] or ""):
        load.log_ingest(conn, SOURCE, sbid, "suspect",
                        detail=f"unparseable game date {parsed['date']!r}")
        return "suspect"
    year = int(parsed["date"][:4])
    if not 1990 <= year <= 2100:
        load.log_ingest(conn, SOURCE, sbid, "suspect",
                        detail=f"implausible game date {parsed['date']}")
        return "suspect"

    load.load_game(conn, parsed, SOURCE, SB.xml_url(sbid), xml, sb_id=str(sbid))
    load.log_ingest(conn, SOURCE, sbid, "ok",
                    season=load.season_of(parsed["date"]), game_date=parsed["date"])
    return "ok"


def run_ingest(conn, date_from, date_to, redo=False, limit=None):
    todo = _pending(conn, date_from, date_to, redo, limit)
    _log(f"ingest: {len(todo)} objects pending in {date_from}..{date_to}")
    counts = {}
    for i, (sbid, lastmod) in enumerate(todo, 1):
        try:
            status = ingest_one(conn, sbid)
            conn.commit()
        except Exception as exc:                      # keep going; record the loss
            conn.rollback()
            load.log_ingest(conn, SOURCE, sbid, "error",
                            detail=f"{type(exc).__name__}: {exc}"[:400])
            conn.commit()
            status = "error"
            _log(f"ingest: sbid={sbid} FAILED {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=1)
        counts[status] = counts.get(status, 0) + 1
        if i % 100 == 0:
            _log(f"ingest: {i}/{len(todo)} -- {counts}")
    _log(f"ingest: done -- {counts}")
    return counts


# -------------------------------------------------------------------- cli ---
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_idx = sub.add_parser("index", help="enumerate the archive bucket")
    p_idx.add_argument("--restart", action="store_true",
                       help="ignore the saved cursor and start from the beginning")
    p_idx.add_argument("--max-pages", type=int, default=None)

    p_ing = sub.add_parser("ingest", help="fetch and load indexed games")
    p_ing.add_argument("--from", dest="date_from", default="2015-01-01")
    p_ing.add_argument("--to", dest="date_to", default="2026-12-31")
    p_ing.add_argument("--redo", action="store_true",
                       help="re-ingest even objects already logged ok")
    p_ing.add_argument("--limit", type=int, default=None)

    args = ap.parse_args(argv)
    conn = load.connect()
    if args.cmd == "index":
        run_index(conn, restart=args.restart, max_pages=args.max_pages)
    else:
        run_ingest(conn, args.date_from, args.date_to,
                   redo=args.redo, limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
