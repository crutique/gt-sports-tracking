"""Collapse duplicate schools and people created before canonicalisation landed.

The first 2023-2026 crawl keyed schools on a weak normaliser and people on exact
full-name match, which fragmented both: 1,553 schools against roughly 300 D1
programmes plus opponents, and 184 people on a single 40-man roster. Season
totals were split across the fragments, so **every rate stat was computed on a
slice of the player's year** -- Advincula's 2026 came out as 57 games and 6
games rather than 61.

This re-keys existing rows with :mod:`pipeline.names` and merges the duplicates
in place, which is much cheaper than re-crawling 28,000 games. It is idempotent:
running it on already-clean data changes nothing.

Order matters. Schools merge first, because two team-seasons cannot merge until
their schools have, and two player-seasons cannot merge until their team-seasons
have. Each stage keeps the **lowest id** as the survivor so the choice is stable
across runs.

    .venv/bin/python -m pipeline.db.repair --dry-run
    .venv/bin/python -m pipeline.db.repair
"""
import argparse
import sys

from pipeline import names
from pipeline.db import load


def _log(msg):
    print(msg, flush=True)


# ----------------------------------------------------------------- schools --
def repair_schools(conn, dry_run=False):
    """Re-key every school and merge those that collapse to the same key."""
    with conn.cursor() as cur:
        cur.execute("SELECT school_id, name FROM cbb.school ORDER BY school_id")
        rows = cur.fetchall()

    survivor = {}                      # canon key -> winning school_id
    merges = []                        # (loser, winner)
    rekey = []                         # (school_id, key)
    for sid, name in rows:
        key = names.canon_school(name)
        if not key:
            continue
        if key in survivor:
            merges.append((sid, survivor[key]))
        else:
            survivor[key] = sid
            rekey.append((sid, key))

    _log(f"schools: {len(rows)} rows -> {len(survivor)} distinct, {len(merges)} merges")
    if dry_run:
        return len(merges)

    with conn.cursor() as cur:
        # Clear keys first: the unique index would otherwise reject the
        # intermediate state while survivors are being re-pointed.
        cur.execute("UPDATE cbb.school SET norm_key = NULL")
        for loser, winner in merges:
            # Both schools may already hold a team-season for the same year --
            # that is precisely what makes them duplicates -- so repointing
            # blindly violates the (school_id, season) key. Fold those together
            # first, then move whatever is left.
            cur.execute(
                "SELECT l.team_season_id, w.team_season_id "
                "FROM cbb.team_season l JOIN cbb.team_season w "
                "  ON w.school_id = %s AND w.season = l.season "
                "WHERE l.school_id = %s", (winner, loser))
            for loser_ts, winner_ts in cur.fetchall():
                _absorb_team_season(cur, loser_ts, winner_ts)
            cur.execute("UPDATE cbb.team_season SET school_id = %s WHERE school_id = %s",
                        (winner, loser))
            cur.execute("DELETE FROM cbb.school WHERE school_id = %s", (loser,))
        cur.executemany("UPDATE cbb.school SET norm_key = %s WHERE school_id = %s",
                        [(k, sid) for sid, k in rekey])
    conn.commit()
    return len(merges)


def _absorb_team_season(cur, loser_ts, winner_ts):
    """Move everything hanging off ``loser_ts`` onto ``winner_ts`` and drop it.

    Player-seasons are repointed rather than merged here; any resulting
    duplicate names are collapsed by :func:`repair_players`, which knows how to
    sum stat lines. Doing it in that order keeps each stage single-purpose.
    """
    cur.execute("UPDATE cbb.player_season SET team_season_id = %s, canon_key = NULL "
                "WHERE team_season_id = %s", (winner_ts, loser_ts))
    for col in ("home_team_season_id", "away_team_season_id"):
        cur.execute(f"UPDATE cbb.game SET {col} = %s WHERE {col} = %s",
                    (winner_ts, loser_ts))
    cur.execute("UPDATE cbb.play SET batting_team_season_id = %s "
                "WHERE batting_team_season_id = %s", (winner_ts, loser_ts))
    cur.execute("DELETE FROM cbb.team_season WHERE team_season_id = %s", (loser_ts,))


# ------------------------------------------------------------ team-seasons --
def repair_team_seasons(conn, dry_run=False):
    """Merge team-seasons left duplicated by the school merge."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT school_id, season, array_agg(team_season_id ORDER BY team_season_id) "
            "FROM cbb.team_season GROUP BY 1,2 HAVING count(*) > 1")
        dupes = cur.fetchall()

    _log(f"team_seasons: {len(dupes)} (school, season) pairs duplicated")
    if dry_run or not dupes:
        return len(dupes)

    with conn.cursor() as cur:
        for _sid, _season, ids in dupes:
            for loser in ids[1:]:
                _absorb_team_season(cur, loser, ids[0])
    conn.commit()
    return len(dupes)


# ---------------------------------------------------------- player-seasons --
def repair_players(conn, dry_run=False):
    """Re-key player-seasons and merge name variants of the same person.

    Stat lines are merged by summing: two fragments of one player's season are
    disjoint sets of games, so adding them reconstructs the real total. The
    ``ON CONFLICT`` guard covers the rare case where both fragments hold a line
    for the same game, which would otherwise double-count.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ps.player_season_id, ps.team_season_id, p.full_name "
            "FROM cbb.player_season ps JOIN cbb.person p USING (person_id) "
            "ORDER BY ps.player_season_id")
        rows = cur.fetchall()

    survivor = {}
    merges, rekey = [], []
    for psid, tsid, full_name in rows:
        key = names.canon_person(full_name)
        if not key:
            continue
        ident = (tsid, key)
        if ident in survivor:
            merges.append((psid, survivor[ident]))
        else:
            survivor[ident] = psid
            rekey.append((psid, key))

    _log(f"player_seasons: {len(rows)} rows -> {len(survivor)} distinct, "
         f"{len(merges)} merges")
    if dry_run:
        return len(merges)

    # Set-based, not row-by-row. 53,857 merges at ~7 statements each is ~377,000
    # round trips, which on a Pi ran for half an hour inside a single opaque
    # transaction with no way to see progress. The same work expressed as joins
    # against a mapping table is about ten statements.
    with conn.cursor() as cur:
        cur.execute("UPDATE cbb.player_season SET canon_key = NULL")
        cur.execute("CREATE TEMP TABLE merge_map (loser bigint PRIMARY KEY, "
                    "winner bigint NOT NULL) ON COMMIT DROP")
        with cur.copy("COPY merge_map (loser, winner) FROM STDIN") as cp:
            for loser, winner in merges:
                cp.write_row((loser, winner))
        cur.execute("CREATE INDEX ON merge_map (winner)")
        _log("  mapping table built; folding stat lines")

        for table, cols in (("batting_line", load._BAT_COLS),
                            ("pitching_line", load._PIT_COLS)):
            names_ = ", ".join(cols)
            sums = ", ".join(f"sum(t.{c})::smallint" for c in cols)
            sets = ", ".join(f"{c} = cbb.{table}.{c} + EXCLUDED.{c}" for c in cols)
            # Several losers can fold into one winner, and the winner may already
            # hold a line for that game -- hence both the GROUP BY and ON CONFLICT.
            cur.execute(
                f"INSERT INTO cbb.{table} (game_id, player_season_id, {names_}) "
                f"SELECT t.game_id, m.winner, {sums} "
                f"FROM cbb.{table} t JOIN merge_map m ON m.loser = t.player_season_id "
                f"GROUP BY t.game_id, m.winner "
                f"ON CONFLICT (game_id, player_season_id) DO UPDATE SET {sets}")
            cur.execute(
                f"DELETE FROM cbb.{table} t USING merge_map m "
                f"WHERE m.loser = t.player_season_id")
            _log(f"  {table} folded")

        for col in ("batter_player_season_id", "pitcher_player_season_id"):
            cur.execute(f"UPDATE cbb.play p SET {col} = m.winner "
                        f"FROM merge_map m WHERE m.loser = p.{col}")
        _log("  plays repointed")

        cur.execute("DELETE FROM cbb.player_season ps USING merge_map m "
                    "WHERE m.loser = ps.player_season_id")
    conn.commit()

    # Re-key in one statement per batch rather than 151,000 individual updates.
    with conn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE rekey_map (psid bigint PRIMARY KEY, key text) "
                    "ON COMMIT DROP")
        with cur.copy("COPY rekey_map (psid, key) FROM STDIN") as cp:
            for psid, key in rekey:
                cp.write_row((psid, key))
        cur.execute("UPDATE cbb.player_season ps SET canon_key = r.key "
                    "FROM rekey_map r WHERE r.psid = ps.player_season_id")
        # people left with no season are the discarded name variants
        cur.execute("DELETE FROM cbb.person p WHERE NOT EXISTS "
                    "(SELECT 1 FROM cbb.player_season ps WHERE ps.person_id = p.person_id)")
    conn.commit()
    _log("  re-keyed and orphan people removed")
    return len(merges)


# ------------------------------------------------------------ duplicate games --
def repair_duplicate_games(conn, dry_run=False):
    """Collapse games loaded more than once from the same archive object.

    Only ~68% of StatCrew files declare `<venue sbid>`, so for the rest the
    ON CONFLICT (sb_id) guard did nothing and a re-ingest inserted another copy.
    Concurrent crawler processes then produced two and three copies of the same
    game, which inflated season totals -- Advincula came out at 63 games against
    an official 61.

    Identity here is the **source URL**: one archive object is one game, whatever
    the document says about itself. That deliberately does not touch legitimate
    doubleheaders, which are distinct objects with distinct URLs.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT gs.url, array_agg(g.game_id ORDER BY g.game_id) "
            "FROM cbb.game g JOIN cbb.game_source gs USING (game_id) "
            "WHERE gs.url IS NOT NULL GROUP BY gs.url HAVING count(*) > 1")
        dupes = cur.fetchall()

    extra = sum(len(ids) - 1 for _u, ids in dupes)
    _log(f"duplicate games: {len(dupes)} source urls loaded more than once, "
         f"{extra} surplus rows")
    if dry_run or not dupes:
        return extra

    with conn.cursor() as cur:
        losers = [gid for _u, ids in dupes for gid in ids[1:]]
        cur.execute("CREATE TEMP TABLE dup_games (game_id bigint PRIMARY KEY) "
                    "ON COMMIT DROP")
        with cur.copy("COPY dup_games (game_id) FROM STDIN") as cp:
            for gid in losers:
                cp.write_row((gid,))
        # every child table cascades from cbb.game, so one delete is enough
        cur.execute("DELETE FROM cbb.game g USING dup_games d "
                    "WHERE d.game_id = g.game_id")
    conn.commit()
    _log(f"  removed {len(losers)} duplicate game rows")
    return extra


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would merge without changing anything")
    args = ap.parse_args(argv)
    conn = load.connect()
    repair_duplicate_games(conn, args.dry_run)
    repair_schools(conn, args.dry_run)
    repair_team_seasons(conn, args.dry_run)
    repair_players(conn, args.dry_run)
    _log("done" if not args.dry_run else "dry run -- nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
