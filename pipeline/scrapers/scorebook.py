"""Scraper for the Northwoods League 'Scorebook' stats platform (pure JSON API).

League stats:  GET {api_base}/statistics/all/0?general=true
Player + log:  GET {api_base}/statistics/player/{player_id}   (404 for unknown ids)
"""
import time

import requests

from pipeline import stats_math as sm

_TIMEOUT = 30
_THROTTLE_S = 1.0
_HEADERS = {"User-Agent": "GT-Summer-Tracker/1.0 (unofficial fan project)"}


def _get_json(url):
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _name(r):
    return f"{r.get('firstname', '')} {r.get('lastname', '')}".strip()


def _norm_bat(r):
    return {
        "stats_id": str(r["player_id"]), "name": _name(r),
        "team": str(r.get("team_abv") or ""),
        "g": r.get("G", 0), "ab": r.get("AB", 0), "r": r.get("R", 0), "h": r.get("H", 0),
        "d": r.get("2B", 0), "t": r.get("3B", 0), "hr": r.get("HR", 0),
        "rbi": r.get("RBI", 0), "bb": r.get("BB", 0), "k": r.get("K", 0),
        "hbp": r.get("HBP", 0), "sb": r.get("SB", 0), "cs": r.get("CS", 0),
        "sf": r.get("SF", 0), "sh": r.get("SH", 0), "pa": r.get("PA", 0),
    }


def _norm_pit(r):
    return {
        "stats_id": str(r["player_id"]), "name": _name(r),
        "team": str(r.get("team_abv") or ""),
        "g": r.get("G", 0), "gs": r.get("GS", 0),
        "ip_outs": sm.ip_str_to_outs(r.get("IP") or 0),
        "w": r.get("W", 0), "l": r.get("L", 0), "sv": r.get("SV", 0), "hld": 0,
        "h": r.get("H", 0), "r": r.get("R", 0), "er": r.get("ER", 0),
        "bb": r.get("BB", 0), "k": r.get("K", 0), "hb": r.get("HB", 0),
        "hr": r.get("HR", 0), "bf": r.get("BF", 0),
    }


def fetch_league_stats(league_cfg):
    data = _get_json(f"{league_cfg['api_base']}/statistics/all/0?general=true")
    types = data["statistics"]["types"]
    return {
        "batting": [_norm_bat(r) for r in types["batting"]["stats"]],
        "pitching": [_norm_pit(r) for r in types["pitching"]["stats"]],
    }


_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _iso_date(short, year):
    parts = str(short).split()
    mon = _MONTHS[parts[0][:3]]
    day = int("".join(ch for ch in parts[1].split("(")[0] if ch.isdigit()))
    return f"{year}-{mon:02d}-{day:02d}"


def _dec(g):
    if g.get("W"):
        return "W"
    if g.get("L"):
        return "L"
    if g.get("SV"):
        return "SV"
    return ""


def _opponent(g):
    if g.get("team") == g.get("home_team"):
        return f"vs {g.get('visitor_team', '')}"
    return f"at {g.get('home_team', '')}"


def _pit_game(g, year):
    return {"date": _iso_date(g["date"], year), "opponent": _opponent(g),
            "ip_outs": sm.ip_str_to_outs(g.get("IP") or 0), "h": g.get("H", 0),
            "r": g.get("R", 0), "er": g.get("ER", 0), "bb": g.get("BB", 0),
            "k": g.get("K", 0), "hr": g.get("HR", 0), "dec": _dec(g)}


def _hit_game(g, year):
    return {"date": _iso_date(g["date"], year), "opponent": _opponent(g),
            "ab": g.get("AB", 0), "r": g.get("R", 0), "h": g.get("H", 0),
            "d": g.get("2B", 0), "t": g.get("3B", 0), "hr": g.get("HR", 0),
            "rbi": g.get("RBI", 0), "bb": g.get("BB", 0), "k": g.get("K", 0),
            "sb": g.get("SB", 0)}


def _player_games(payload):
    types = payload.get("playerStats", {}).get("types", {})
    out = []
    for side, mk in (("pitching", _pit_game), ("batting", _hit_game)):
        games_by_year = (types.get(side) or {}).get("games") or {}
        if not games_by_year:
            continue
        year = max(games_by_year, key=int)
        out.extend(mk(g, year) for g in games_by_year[year])
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


def fetch_game_logs(league_cfg, stats_ids):
    logs = {}
    for sid in stats_ids:
        if not str(sid).isdigit():
            logs[sid] = []   # placeholder id — player not yet located on this platform
            continue
        try:
            payload = _get_json(f"{league_cfg['api_base']}/statistics/player/{sid}")
            logs[sid] = _player_games(payload)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logs[sid] = []
            else:
                raise
        time.sleep(_THROTTLE_S)
    return logs
