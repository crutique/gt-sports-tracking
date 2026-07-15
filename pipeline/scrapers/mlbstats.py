"""Scraper for leagues on MLB's public StatsAPI (statsapi.mlb.com).

Covers the Cape Cod Baseball League (leagueId 565) and Appalachian League
(leagueId 120), both under sportId 22 (College/Amateur Baseball).

League stats:  GET {api_base}/stats?stats=season&group={g}&sportId={s}&leagueId={l}&season={y}&playerPool=all&limit=2000
Player log:    GET {api_base}/people/{id}/stats?stats=gameLog&group=hitting,pitching&season={y}&sportId={s}
               (log spans ALL sportId-22 leagues incl. college — filtered by league.id)
"""
import datetime
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


def _season(cfg):
    return cfg.get("season") or datetime.date.today().year


def _splits(payload):
    for block in payload.get("stats", []):
        yield from block.get("splits", [])


def _base_row(split):
    return {
        "stats_id": str(split["player"]["id"]),
        "name": split["player"].get("fullName", ""),
        "team": (split.get("team") or {}).get("name", ""),
    }


def _norm_bat(split):
    s = split.get("stat", {})
    row = _base_row(split)
    row.update({
        "g": s.get("gamesPlayed", 0), "ab": s.get("atBats", 0), "r": s.get("runs", 0),
        "h": s.get("hits", 0), "d": s.get("doubles", 0), "t": s.get("triples", 0),
        "hr": s.get("homeRuns", 0), "rbi": s.get("rbi", 0), "bb": s.get("baseOnBalls", 0),
        "k": s.get("strikeOuts", 0), "hbp": s.get("hitByPitch", 0),
        "sb": s.get("stolenBases", 0), "cs": s.get("caughtStealing", 0),
        "sf": s.get("sacFlies", 0), "sh": s.get("sacBunts", 0),
        "pa": s.get("plateAppearances", 0),
    })
    return row


def _norm_pit(split):
    s = split.get("stat", {})
    row = _base_row(split)
    row.update({
        "g": s.get("gamesPlayed", 0), "gs": s.get("gamesStarted", 0),
        "ip_outs": sm.ip_str_to_outs(s.get("inningsPitched") or 0),
        "w": s.get("wins", 0), "l": s.get("losses", 0), "sv": s.get("saves", 0),
        "hld": s.get("holds", 0), "h": s.get("hits", 0), "r": s.get("runs", 0),
        "er": s.get("earnedRuns", 0), "bb": s.get("baseOnBalls", 0),
        "k": s.get("strikeOuts", 0), "hb": s.get("hitBatsmen", 0),
        "hr": s.get("homeRuns", 0), "bf": s.get("battersFaced", 0),
    })
    return row


def fetch_league_stats(league_cfg):
    base, sport = league_cfg["api_base"], league_cfg.get("sport_id", 22)
    lid, season = league_cfg["league_id"], _season(league_cfg)
    out = {}
    for group, norm, key in (("hitting", _norm_bat, "batting"),
                             ("pitching", _norm_pit, "pitching")):
        url = (f"{base}/stats?stats=season&group={group}&sportId={sport}"
               f"&leagueId={lid}&season={season}&playerPool=all&limit=2000")
        out[key] = [norm(s) for s in _splits(_get_json(url))]
    return out


def _opponent(split):
    name = (split.get("opponent") or {}).get("name", "")
    return f"vs {name}" if split.get("isHome") else f"at {name}"


def _pit_game(split):
    s = split.get("stat", {})
    dec = "W" if s.get("wins") else "L" if s.get("losses") else "SV" if s.get("saves") else ""
    return {"date": split.get("date", ""), "opponent": _opponent(split),
            "ip_outs": sm.ip_str_to_outs(s.get("inningsPitched") or 0),
            "h": s.get("hits", 0), "r": s.get("runs", 0), "er": s.get("earnedRuns", 0),
            "bb": s.get("baseOnBalls", 0), "k": s.get("strikeOuts", 0),
            "hr": s.get("homeRuns", 0), "dec": dec}


def _hit_game(split):
    s = split.get("stat", {})
    return {"date": split.get("date", ""), "opponent": _opponent(split),
            "ab": s.get("atBats", 0), "r": s.get("runs", 0), "h": s.get("hits", 0),
            "d": s.get("doubles", 0), "t": s.get("triples", 0), "hr": s.get("homeRuns", 0),
            "rbi": s.get("rbi", 0), "bb": s.get("baseOnBalls", 0),
            "k": s.get("strikeOuts", 0), "sb": s.get("stolenBases", 0)}


def fetch_game_logs(league_cfg, stats_ids):
    base, sport = league_cfg["api_base"], league_cfg.get("sport_id", 22)
    lid, season = league_cfg["league_id"], _season(league_cfg)
    logs = {}
    for sid in stats_ids:
        if not str(sid).isdigit():
            logs[sid] = []
            continue
        try:
            payload = _get_json(f"{base}/people/{sid}/stats?stats=gameLog"
                                f"&group=hitting,pitching&season={season}&sportId={sport}")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logs[sid] = []
                time.sleep(_THROTTLE_S)
                continue
            raise
        entries = []
        for block in payload.get("stats", []):
            group = block.get("group", {}).get("displayName")
            mk = _pit_game if group == "pitching" else _hit_game
            for split in block.get("splits", []):
                if (split.get("league") or {}).get("id") == lid:
                    entries.append(mk(split))
        entries.sort(key=lambda e: e["date"], reverse=True)
        logs[sid] = entries
        time.sleep(_THROTTLE_S)
    return logs
