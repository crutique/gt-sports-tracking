"""Client for NCAA.com's own public data backend — the source of record for D1
college baseball (free, unauthenticated, no bot wall).

This is the same API ncaa.com's gamecenter calls. Three GraphQL operations on
``sdataprod.ncaa.com``, addressed by *persisted query* (the server stores the
query; callers send only its sha256 + variables):

  contests(date)     GetContests_web                            -> the day's games
  boxscore(id)       NCAA_GetGamecenterBoxscoreBaseballById_web -> per-player game lines
  playbyplay(id)     NCAA_GetGamecenterPbpGenericById_web       -> narrative play text

Season leaderboards are plain server-rendered HTML and live in :mod:`ncaa_stats`.

**Re-discovering the SHAs.** NCAA rotates them on frontend releases. They are
published in any gamecenter page's own settings blob: fetch
``https://www.ncaa.com/game/{contest_id}``, read the
``<script data-drupal-selector="drupal-settings-json">`` JSON, and take
``.gamecenter.gqlShas`` (per-sport boxscore/pbp/teamStats) and ``.core.gqlHost``.
Scoreboard SHAs are at ``.scoreboardWidget.shas``. :func:`discover_shas` does this;
if an operation starts returning ``PersistedQueryNotFound``, refresh and update
:data:`SHAS`.

**Caching.** Completed games are immutable, so responses for final games are
cached on disk forever — a season backfill is paid for once. Live games are never
cached.
"""
import hashlib
import json
import re
import time
from pathlib import Path

import requests

GQL_HOST = "https://sdataprod.ncaa.com"
_TIMEOUT = 30
_THROTTLE_S = 0.7          # be a good citizen; ncaa.com's own page polls at 10s
_HEADERS = {
    "User-Agent": "GT-Summer-Tracker/1.0 (unofficial fan project)",
    "Referer": "https://www.ncaa.com/",
}
CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "ncaa"

# Verified 2026-07-25. See module docstring to refresh.
SHAS = {
    "GetContests_web":
        "4bcb5e6432fa9da365c0c19af01b1f9015cc7eb5c21e7af2dba308784a166df7",
    "NCAA_GetGamecenterBoxscoreBaseballById_web":
        "5e92118b2f424040aa96067aba6d34e882165aaf02e9e73cb9d69317066c6ae8",
    "NCAA_GetGamecenterPbpGenericById_web":
        "57f922d56d60d88326b62202b3d88e8cd3cfb6687931bc0b5b3dfab089b84faa",
}

SPORT_CODE = "MBA"          # men's baseball
_last_call = [0.0]


def season_year(season):
    """NCAA's ``seasonYear`` is the ACADEMIC start year: the 2026 season is 2025."""
    return season - 1


def _throttle():
    delta = time.monotonic() - _last_call[0]
    if delta < _THROTTLE_S:
        time.sleep(_THROTTLE_S - delta)
    _last_call[0] = time.monotonic()


def _cache_path(op, variables):
    key = hashlib.sha1(f"{op}:{json.dumps(variables, sort_keys=True)}".encode()).hexdigest()
    return CACHE_DIR / op / f"{key}.json"


def query(op, variables, cache=True):
    """Run a persisted GraphQL operation. Returns the ``data`` payload."""
    path = _cache_path(op, variables)
    if cache and path.exists():
        return json.loads(path.read_text())

    sha = SHAS.get(op)
    if not sha:
        raise KeyError(f"No persisted-query sha for {op!r}; run discover_shas()")
    _throttle()
    # NOTE: compact separators are required — the gateway rejects the whitespace
    # json.dumps emits by default (HTTP 500).
    compact = lambda o: json.dumps(o, separators=(",", ":"))
    resp = requests.get(GQL_HOST, params={
        "meta": op,
        "extensions": compact({"persistedQuery": {"version": 1, "sha256Hash": sha}}),
        "variables": compact(variables),
    }, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"{op} failed: {json.dumps(body['errors'])[:300]}")
    data = body.get("data") or {}
    if cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    return data


def discover_shas(contest_id):
    """Read current persisted-query SHAs out of a live gamecenter page."""
    _throttle()
    html = requests.get(f"https://www.ncaa.com/game/{contest_id}",
                        headers=_HEADERS, timeout=_TIMEOUT).text
    m = re.search(r'<script type="application/json" '
                  r'data-drupal-selector="drupal-settings-json">(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("drupal settings blob not found on gamecenter page")
    settings = json.loads(m.group(1))
    return dict(settings.get("gamecenter", {}).get("gqlShas") or {})


def contests(date, season, division=1):
    """Every D1 game on ``date`` (a ``datetime.date``). Includes contestId + teams."""
    data = query("GetContests_web", {
        "sportCode": SPORT_CODE,
        "division": division,
        "seasonYear": season_year(season),
        "contestDate": date.strftime("%m/%d/%Y"),
        "week": None,
    }, cache=True)
    return data.get("contests") or []


def _is_final(payload, key):
    return str((payload.get(key) or {}).get("status") or "").upper().startswith("F")


def boxscore(contest_id, cache=True):
    """Per-player game lines (all players — no leaderboard cap)."""
    data = query("NCAA_GetGamecenterBoxscoreBaseballById_web",
                 {"contestId": int(contest_id), "staticTestEnv": None},
                 cache=cache and True)
    return data.get("boxscore") or {}


def playbyplay(contest_id, cache=True):
    """Narrative play text — the exact-event layer (HBP / SF / SH live only here)."""
    data = query("NCAA_GetGamecenterPbpGenericById_web",
                 {"contestId": int(contest_id), "staticTestEnv": None},
                 cache=cache and True)
    return data.get("playbyplay") or {}


def iter_plays(pbp):
    """Flatten a play-by-play payload to ``(inning, half_team_id, play_text)``.

    ``periods[].playbyplayStats[].plays[].playText`` — each ``playbyplayStats``
    entry carries the ``teamId`` batting in that half-inning.
    """
    for period in pbp.get("periods") or []:
        inning = period.get("periodNumber")
        for half in period.get("playbyplayStats") or []:
            team_id = half.get("teamId")
            for play in half.get("plays") or []:
                text = (play.get("playText") or "").strip()
                if text:
                    yield inning, team_id, text
