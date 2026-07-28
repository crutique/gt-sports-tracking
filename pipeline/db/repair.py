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

    with conn.cursor() as cur:
        cur.execute("UPDATE cbb.player_season SET canon_key = NULL")
        for loser, winner in merges:
            for table, cols in (("batting_line", load._BAT_COLS),
                                ("pitching_line", load._PIT_COLS)):
                sets = ", ".join(f"{c} = cbb.{table}.{c} + EXCLUDED.{c}" for c in cols)
                names_ = ", ".join(cols)
                cur.execute(
                    f"INSERT INTO cbb.{table} (game_id, player_season_id, {names_}) "
                    f"SELECT game_id, %s, {names_} FROM cbb.{table} "
                    f"WHERE player_season_id = %s "
                    f"ON CONFLICT (game_id, player_season_id) DO UPDATE SET {sets}",
                    (winner, loser))
                cur.execute(f"DELETE FROM cbb.{table} WHERE player_season_id = %s",
                            (loser,))
            for col in ("batter_player_season_id", "pitcher_player_season_id"):
                cur.execute(f"UPDATE cbb.play SET {col} = %s WHERE {col} = %s",
                            (winner, loser))
            cur.execute("DELETE FROM cbb.player_season WHERE player_season_id = %s",
                        (loser,))
        cur.executemany("UPDATE cbb.player_season SET canon_key = %s "
                        "WHERE player_season_id = %s",
                        [(k, psid) for psid, k in rekey])
        # people left with no season are the discarded name variants
        cur.execute("DELETE FROM cbb.person p WHERE NOT EXISTS "
                    "(SELECT 1 FROM cbb.player_season ps WHERE ps.person_id = p.person_id)")
    conn.commit()
    return len(merges)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would merge without changing anything")
    args = ap.parse_args(argv)
    conn = load.connect()
    repair_schools(conn, args.dry_run)
    repair_team_seasons(conn, args.dry_run)
    repair_players(conn, args.dry_run)
    _log("done" if not args.dry_run else "dry run -- nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
