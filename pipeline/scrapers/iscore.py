"""Scraper for leagues on the iScore Sports platform (pure JSON API).

Covers the South Florida Collegiate Baseball League (SFCBL).

Teams:       GET {api_base}/public/leagues/{league_id}/teams
League pool: GET {api_base}/player-stats?teamId={T}&seasonId={S}   (one call per team;
             the leaderboard endpoints cap at 100 rows, so team pools are authoritative)
Games list:  GET {api_base}/public/games?leagueId={L}&playerId={P}&take=200&startDateFrom=...&startDateTo=...
Box score:   GET {api_base}/public/games/{guid}/boxScore/gzip      (gzipped JSON body)
"""
import datetime
import gzip
import json
import time
import uuid

import requests

_TIMEOUT = 30
_THROTTLE_S = 1.0
_HEADERS = {"User-Agent": "GT-Summer-Tracker/1.0 (unofficial fan project)"}

_STATUS_PLAYED = 3   # gameStatusId: 3 = played, 2 = scheduled/postponed


def _get_json(url):
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _get_bytes(url):
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.content


def _gunzip_json(raw):
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def _season(cfg):
    return cfg.get("season") or datetime.date.today().year


def _is_guid(sid):
    try:
        uuid.UUID(str(sid))
        return True
    except ValueError:
        return False


def _overall(player, category):
    """stats.{category}.overall with every level nullable (stats: {} / null happens)."""
    return ((player.get("stats") or {}).get(category) or {}).get("overall") or {}


def _n(block, key):
    return block.get(key) or 0


def _name(p):
    return f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()


def _norm_bat(p, team_name):
    b, r = _overall(p, "batting"), _overall(p, "running")
    return {
        "stats_id": str(p["playerId"]), "name": _name(p), "team": team_name,
        "g": _n(b, "GP"), "ab": _n(b, "AB"), "r": _n(b, "R"), "h": _n(b, "H"),
        "d": _n(b, "2B"), "t": _n(b, "3B"), "hr": _n(b, "HR"), "rbi": _n(b, "RBI"),
        "bb": _n(b, "BB"), "k": _n(b, "SO"), "hbp": _n(b, "HBP"),
        "sb": _n(r, "SB"), "cs": _n(r, "CS"),
        "sf": _n(b, "SF"), "sh": _n(b, "SH"), "pa": _n(b, "PA"),
    }


def _norm_pit(p, team_name):
    s = _overall(p, "pitching")
    return {
        "stats_id": str(p["playerId"]), "name": _name(p), "team": team_name,
        "g": _n(s, "GP"), "gs": _n(s, "GS"), "ip_outs": _n(s, "OUTS_PITCHED"),
        "w": _n(s, "W"), "l": _n(s, "L"), "sv": _n(s, "SV"), "hld": _n(s, "HLD"),
        "h": _n(s, "H"), "r": _n(s, "R"), "er": _n(s, "ER"), "bb": _n(s, "BB"),
        "k": _n(s, "SO"), "hb": _n(s, "HBP"), "hr": _n(s, "HR"), "bf": _n(s, "BF"),
    }


def fetch_league_stats(league_cfg):
    base, lid = league_cfg["api_base"], league_cfg["league_id"]
    season_id = league_cfg["season_id"]
    teams = _get_json(f"{base}/public/leagues/{lid}/teams")
    batting, pitching = [], []
    for team in teams:
        players = _get_json(f"{base}/player-stats?teamId={team['guid']}&seasonId={season_id}")
        for p in players:
            bat = _overall(p, "batting")
            if _n(bat, "PA") or _n(bat, "AB"):
                batting.append(_norm_bat(p, team.get("name", "")))
            pit = _overall(p, "pitching")
            if _n(pit, "BF") or _n(pit, "OUTS_PITCHED"):
                pitching.append(_norm_pit(p, team.get("name", "")))
        time.sleep(_THROTTLE_S)
    return {"batting": batting, "pitching": pitching}


def _opponent(game, is_home):
    if is_home:
        return f"vs {(game.get('awayTeam') or {}).get('name', '')}"
    return f"at {(game.get('homeTeam') or {}).get('name', '')}"


def _pit_game(date, opponent, s):
    dec = "W" if _n(s, "W") else "L" if _n(s, "L") else "SV" if _n(s, "SV") else ""
    return {"date": date, "opponent": opponent, "ip_outs": _n(s, "OUTS_PITCHED"),
            "h": _n(s, "H"), "r": _n(s, "R"), "er": _n(s, "ER"), "bb": _n(s, "BB"),
            "k": _n(s, "SO"), "hr": _n(s, "HR"), "dec": dec}


def _hit_game(date, opponent, b, r):
    return {"date": date, "opponent": opponent,
            "ab": _n(b, "AB"), "r": _n(b, "R"), "h": _n(b, "H"), "d": _n(b, "2B"),
            "t": _n(b, "3B"), "hr": _n(b, "HR"), "rbi": _n(b, "RBI"),
            "bb": _n(b, "BB"), "k": _n(b, "SO"), "sb": _n(r, "SB")}


def fetch_game_logs(league_cfg, stats_ids):
    base, lid, season = league_cfg["api_base"], league_cfg["league_id"], _season(league_cfg)
    boxscores = {}   # gameGuid -> payload; teammates share games, fetch each box once

    def _boxscore(guid):
        if guid not in boxscores:
            boxscores[guid] = _gunzip_json(_get_bytes(f"{base}/public/games/{guid}/boxScore/gzip"))
            time.sleep(_THROTTLE_S)
        return boxscores[guid]

    logs = {}
    for sid in stats_ids:
        if not _is_guid(sid):
            logs[sid] = []   # placeholder id — player not yet located on this platform
            continue
        try:
            games = _get_json(
                f"{base}/public/games?leagueId={lid}&playerId={sid}&take=200"
                f"&startDateFrom={season}-05-01T00:00:00.000Z"
                f"&startDateTo={season}-08-01T00:00:00.000Z")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logs[sid] = []
                time.sleep(_THROTTLE_S)
                continue
            raise
        entries = []
        for game in games:
            if game.get("gameStatusId") != _STATUS_PLAYED:
                continue   # scheduled/postponed games don't belong in logs
            box = _boxscore(game["gameGuid"])
            player = ((box.get("gameStatState") or {}).get("players") or {}).get(str(sid))
            if not player:
                continue   # listed game without a stat line for this player
            date = str(game.get("scheduledDate", ""))[:10]
            is_home = player.get("teamId") == (game.get("homeTeam") or {}).get("id")
            opp = _opponent(game, is_home)
            pit = _overall(player, "pitching")
            if _n(pit, "BF") or _n(pit, "OUTS_PITCHED"):
                entries.append(_pit_game(date, opp, pit))
            bat = _overall(player, "batting")
            if _n(bat, "PA") or _n(bat, "AB"):
                entries.append(_hit_game(date, opp, bat, _overall(player, "running")))
        entries.sort(key=lambda e: e["date"], reverse=True)
        logs[sid] = entries
        time.sleep(_THROTTLE_S)
    return logs
