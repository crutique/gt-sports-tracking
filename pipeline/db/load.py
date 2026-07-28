"""Load a parsed StatCrew game into the ``cbb`` schema.

Idempotent by design: the backfill runs for days over ~100k games, will be
interrupted, and must be safe to restart. Every write is an upsert keyed on a
natural identifier, so re-loading a game corrects it rather than duplicating it.

**Identity is resolved conservatively.** StatCrew records whatever the scorer
typed, and that varies per school and per game. Schools are matched on a
normalised name; people are matched on full name *within a single team-season*,
which is safe because a roster rarely carries two identical full names. Play
rows keep the scored name verbatim alongside a nullable resolved FK, so a bad
match can be re-run later without re-fetching anything.

**A game is only as trustworthy as its receipt**, so `cbb.game_source` is written
in the same transaction as the game: source name, URL, fetch time, and a sha256
of the exact bytes parsed.
"""
import re

import psycopg

DSN = "dbname=ncaa_baseball"


def connect(dsn=DSN):
    return psycopg.connect(dsn)


def season_of(game_date):
    """Season is the spring year: a 2026-02-15 game belongs to the 2026 season.

    Everything after June is treated as the next season's fall activity, which
    keeps exhibition/fall dates from being filed a year early.
    """
    year, month = int(game_date[:4]), int(game_date[5:7])
    return year + 1 if month >= 8 else year


_PUNCT = re.compile(r"[^a-z0-9]+")


def norm_name(name):
    """Normalise a school name enough to match across scorer spellings."""
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"\b(university|univ|college|the|of|at)\b", " ", s)
    s = re.sub(r"\bst\.?\b", "state", s)
    return _PUNCT.sub("", s)


# --------------------------------------------------------------- resolvers --
def school_id(cur, name, code=None):
    key = norm_name(name)
    cur.execute("SELECT school_id FROM cbb.school WHERE norm_key = %s", (key,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO cbb.school (name, short_name, norm_key) VALUES (%s, %s, %s) "
        "ON CONFLICT (norm_key) DO UPDATE SET name = EXCLUDED.name "
        "RETURNING school_id", (name, code, key))
    return cur.fetchone()[0]


def team_season_id(cur, sid, season):
    cur.execute(
        "INSERT INTO cbb.team_season (school_id, season) VALUES (%s, %s) "
        "ON CONFLICT (school_id, season) DO UPDATE SET school_id = EXCLUDED.school_id "
        "RETURNING team_season_id", (sid, season))
    return cur.fetchone()[0]


def player_season_id(cur, player, tsid):
    """Resolve one roster entry, creating the person on first sight.

    Matching is on full name *within this team-season only* -- never globally,
    which would merge distinct people who share a name across schools.
    """
    name = player["name"] or player["shortname"]
    cur.execute(
        "SELECT ps.player_season_id FROM cbb.player_season ps "
        "JOIN cbb.person p ON p.person_id = ps.person_id "
        "WHERE ps.team_season_id = %s AND lower(p.full_name) = lower(%s)",
        (tsid, name))
    row = cur.fetchone()
    if row:
        return row[0]

    parts = name.rsplit(" ", 1)
    cur.execute(
        "INSERT INTO cbb.person (full_name, first_name, last_name, bats, throws) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING person_id",
        (name, parts[0] if len(parts) > 1 else None, parts[-1],
         player.get("bats") or None, player.get("throws") or None))
    pid = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO cbb.player_season "
        "(person_id, team_season_id, jersey, positions, class, bats, throws) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (person_id, team_season_id) DO UPDATE SET jersey = EXCLUDED.jersey "
        "RETURNING player_season_id",
        (pid, tsid, player.get("uni") or None, player.get("pos") or None,
         player.get("cls") or None, player.get("bats") or None,
         player.get("throws") or None))
    return cur.fetchone()[0]


# ------------------------------------------------------------------- lines --
_BAT_COLS = ("ab", "r", "h", "d", "t", "hr", "rbi", "bb", "k", "hbp",
             "sf", "sh", "sb", "cs", "gdp", "kl")
_PIT_COLS = ("ip_outs", "h", "r", "er", "bb", "k", "hb", "hr", "bf", "ab",
             "sfa", "sha", "ibb", "kl", "pitches", "strikes", "w", "l", "gs")


def _upsert_line(cur, table, cols, game_id, psid, row):
    names = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols)
    cur.execute(
        f"INSERT INTO cbb.{table} (game_id, player_season_id, {names}) "
        f"VALUES (%s, %s, {marks}) "
        f"ON CONFLICT (game_id, player_season_id) DO UPDATE SET {updates}",
        [game_id, psid] + [int(row.get(c) or 0) for c in cols])


# -------------------------------------------------------------------- game --
def load_game(conn, parsed, source, url, raw_text, sha=None):
    """Upsert one parsed game and everything hanging off it. Returns game_id."""
    from pipeline import statbroadcast as SB

    season = season_of(parsed["date"])
    with conn.cursor() as cur:
        sides = {}
        for side in ("away", "home"):
            team = parsed[side]
            sid = school_id(cur, team["name"], team.get("id"))
            sides[side] = (team, team_season_id(cur, sid, season))

        away, away_ts = sides["away"]
        home, home_ts = sides["home"]

        cur.execute(
            "INSERT INTO cbb.game (season, game_date, start_time, "
            " home_team_season_id, away_team_season_id, home_runs, away_runs, "
            " stadium, location, attendance, duration, status, is_complete, "
            " sb_id, statcrew_gameid, updated_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now()) "
            "ON CONFLICT (sb_id) WHERE sb_id IS NOT NULL DO UPDATE SET "
            " home_runs = EXCLUDED.home_runs, away_runs = EXCLUDED.away_runs, "
            " status = EXCLUDED.status, is_complete = EXCLUDED.is_complete, "
            " attendance = EXCLUDED.attendance, updated_at = now() "
            "RETURNING game_id",
            (season, parsed["date"], parsed.get("start") or None,
             home_ts, away_ts, home["runs"], away["runs"],
             parsed.get("stadium") or None, parsed.get("location") or None,
             parsed.get("attend") or None, parsed.get("duration") or None,
             "final" if parsed.get("complete") else "in_progress",
             bool(parsed.get("complete")),
             parsed.get("sbid") or None, parsed.get("gameid") or None))
        game_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO cbb.game_source "
            " (game_id, source, url, content_sha256, byte_length) "
            "VALUES (%s,%s,%s,%s,%s) "
            "ON CONFLICT (game_id, source) DO UPDATE SET "
            " url = EXCLUDED.url, content_sha256 = EXCLUDED.content_sha256, "
            " byte_length = EXCLUDED.byte_length, fetched_at = now()",
            (game_id, source, url, sha or SB.sha256(raw_text), len(raw_text)))

        psid_by_name = {}
        for side, (team, tsid) in sides.items():
            for p in team["players"]:
                psid = player_season_id(cur, p, tsid)
                psid_by_name[(side, p["shortname"] or p["name"])] = psid
                _upsert_line(cur, "batting_line", _BAT_COLS, game_id, psid, p["batting"])
                if p["pitching"]:
                    _upsert_line(cur, "pitching_line", _PIT_COLS, game_id, psid, p["pitching"])

        # Plays are replaced wholesale: a live game's tail changes as it is
        # re-polled, and a completed reload should not leave orphans behind.
        cur.execute("DELETE FROM cbb.play WHERE game_id = %s", (game_id,))
        ts_by_vh = {"V": away_ts, "H": home_ts}
        side_by_vh = {"V": "away", "H": "home"}
        rows = []
        # `ordinal` is assigned here, not taken from the file: scorers repeat and
        # skip `seq` values, so it cannot serve as a key.
        for ordinal, pl in enumerate(parsed["plays"], 1):
            side = side_by_vh.get(pl["half"])
            rows.append((
                game_id, ordinal, pl["seq"], pl["inning"], pl["half"],
                ts_by_vh.get(pl["half"]), pl["outs"],
                pl["bases"]["first"], pl["bases"]["second"], pl["bases"]["third"],
                pl["batter"], pl["batterHand"] or None,
                pl["pitcher"], pl["pitcherHand"] or None,
                pl["count"]["balls"], pl["count"]["strikes"],
                pl["pitches"] or None, pl["text"],
                psid_by_name.get((side, pl["batter"])),
            ))
        if rows:
            cur.executemany(
                "INSERT INTO cbb.play (game_id, ordinal, seq, inning, half, "
                " batting_team_season_id, outs_before, runner_first, runner_second, "
                " runner_third, batter_name, batter_hand, pitcher_name, pitcher_hand, "
                " balls, strikes, pitch_sequence, description, batter_player_season_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
    return game_id


def log_ingest(conn, source, key, status, season=None, game_date=None, detail=None):
    """Record an attempt -- including the ones that found nothing.

    The gap list is a product, not an accident: a game we could not retrieve has
    to be visible rather than silently absent.
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO cbb.ingest_log (source, key, season, game_date, status, detail) "
            "VALUES (%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (source, key) DO UPDATE SET status = EXCLUDED.status, "
            " detail = EXCLUDED.detail, attempted_at = now()",
            (source, str(key), season, game_date, status, detail))
