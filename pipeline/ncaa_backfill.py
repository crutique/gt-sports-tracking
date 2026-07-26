"""Pull season stat rows out of the NCAA feed for a team, or for the whole D1 pool.

Exploits the cumulative property established in :mod:`pipeline.ncaa_season`: a
player's season line is the maximum of their ``hittingSeason`` across games, so a
complete season only requires games *late* enough that every player has reached
their final totals. Building the D1 percentile pool therefore costs a few
thousand box scores instead of a full season's ~18,000 — and every response is
cached permanently, so the cost is paid once.

CLI::

    python -m pipeline.ncaa_backfill team georgia-tech 2026 out.json
    python -m pipeline.ncaa_backfill pool 2026 pool.json --from 05-15 --to 06-22
"""
import datetime
import json
import sys

from pipeline import ncaa_api as api
from pipeline import ncaa_season as season


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += datetime.timedelta(days=1)


def scan_contests(season_year, start, end, division=1, progress=None):
    """All contests in a window, plus a seoname -> teamId-ish index."""
    contests = []
    for d in daterange(start, end):
        try:
            found = api.contests(d, season=season_year, division=division)
        except Exception as e:                      # a bad day shouldn't kill a run
            if progress:
                progress(f"  {d}: {type(e).__name__} {str(e)[:60]}")
            continue
        contests.extend(found)
        if progress:
            progress(f"  {d}: {len(found)} contests")
    return contests


def team_contest_ids(contests, seoname):
    return [c["contestId"] for c in contests
            if any(t.get("seoname") == seoname for t in c.get("teams", []))]


def load_games(contest_ids, want_pbp=True, progress=None):
    """``[(boxscore, pbp)]`` for the given contests, skipping unusable ones."""
    games = []
    for i, gid in enumerate(contest_ids, 1):
        try:
            box = api.boxscore(gid)
            pbp = api.playbyplay(gid) if want_pbp else {}
        except Exception as e:
            if progress:
                progress(f"  skip {gid}: {type(e).__name__} {str(e)[:60]}")
            continue
        games.append((box, pbp))
        if progress and i % 25 == 0:
            progress(f"  ...{i}/{len(contest_ids)} games")
    return games


def team_id_for(box, seoname):
    for t in box.get("teams") or []:
        if t.get("seoname") == seoname:
            try:
                return int(t["teamId"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def team_season_rows(seoname, season_year, start, end, progress=None):
    """Canonical season rows for one team."""
    contests = scan_contests(season_year, start, end, progress=progress)
    ids = team_contest_ids(contests, seoname)
    if progress:
        progress(f"  {seoname}: {len(ids)} contests")
    games = load_games(ids, progress=progress)
    team_id = next((tid for box, _ in games
                    if (tid := team_id_for(box, seoname)) is not None), None)
    if team_id is None:
        return [], None
    return season.team_season(games, team_id), team_id


def _season_bounds(season_year):
    """Default scan window for a college baseball season (Feb -> late June)."""
    return datetime.date(season_year, 2, 1), datetime.date(season_year, 6, 30)


def _parse_md(s, year):
    m, d = s.split("-")
    return datetime.date(year, int(m), int(d))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    mode = argv[0]
    log = lambda m: print(m, flush=True)

    if mode == "team":
        seoname, year, out = argv[1], int(argv[2]), argv[3]
        start, end = _season_bounds(year)
        rows, team_id = team_season_rows(seoname, year, start, end, progress=log)
        payload = {"source": "ncaa.com sdataprod (boxscore cumulative + pbp events)",
                   "season": year, "team": seoname, "teamId": team_id, "players": rows}
        with open(out, "w") as fh:
            json.dump(payload, fh, indent=1)
        log(f"wrote {len(rows)} players -> {out}")
        return 0

    if mode == "pool":
        year, out = int(argv[1]), argv[2]
        start, end = _season_bounds(year)
        if "--from" in argv:
            start = _parse_md(argv[argv.index("--from") + 1], year)
        if "--to" in argv:
            end = _parse_md(argv[argv.index("--to") + 1], year)
        tail = int(argv[argv.index("--tail") + 1]) if "--tail" in argv else 4
        log(f"scanning contests {start} .. {end}")
        contests = scan_contests(year, start, end, progress=log)
        # Cumulative totals mean only each team's LAST few games are needed, so
        # fetch those rather than the whole window (~900 games instead of ~6,900).
        by_team = {}
        for c in contests:
            for t in c.get("teams") or []:
                seo = t.get("seoname")
                if seo:
                    by_team.setdefault(seo, []).append(c)
        ids = set()
        for seo, cs in by_team.items():
            cs.sort(key=lambda c: (c.get("startDate") or "", c["contestId"]))
            ids.update(c["contestId"] for c in cs[-tail:])
        ids = sorted(ids)
        log(f"{len(by_team)} teams; last {tail} games each -> "
            f"{len(ids)} distinct contests; loading box scores (no pbp)...")
        games = load_games(ids, want_pbp=False, progress=log)
        # every team that appears, keyed by its numeric id
        team_ids = set()
        for box, _ in games:
            for t in box.get("teams") or []:
                try:
                    team_ids.add(int(t["teamId"]))
                except (KeyError, TypeError, ValueError):
                    pass
        log(f"{len(team_ids)} teams; aggregating...")
        players = []
        for tid in sorted(team_ids):
            players.extend(season.team_season(games, tid))
        payload = {"source": "ncaa.com sdataprod (boxscore cumulative)",
                   "season": year, "window": [str(start), str(end)],
                   "teams": len(team_ids), "players": players}
        with open(out, "w") as fh:
            json.dump(payload, fh)
        log(f"wrote {len(players)} players from {len(team_ids)} teams -> {out}")
        return 0

    print(f"unknown mode {mode!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
