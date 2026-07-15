# GT Summer Tracker — Plan 4: MLB StatsAPI Scraper (Cape Cod + Appalachian) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Live stats for the 8 Cape Cod League players and Judson Hartwell (Appalachian League) via one new `mlbstats` platform scraper against MLB's public StatsAPI.

**Architecture:** Both leagues run on statsapi.mlb.com (sportId 22, leagueId 565 = CCBL / 120 = Appalachian). One platform module normalizes season splits to the canonical row contract (native PA, BF, and — new — HLD) and per-player game logs (filtered by `league.id`, since sportId-22 logs include college games). Same fixture-based offline testing and per-league isolation as `scorebook`.

**Tech Stack:** Python 3.12 (`.venv` — NEVER bare `python3`, it's 3.7), requests, pytest. No site changes required (stats appear automatically).

**PREREQUISITE:** the `site-updates` branch (class years, positions, photos) must be merged to main first — this plan edits `pipeline/players.yaml` and would conflict.

**Verified live API facts (scouted 2026-07-15, plan written against them):**
- League season stats: `GET https://statsapi.mlb.com/api/v1/stats?stats=season&group={hitting|pitching}&sportId=22&leagueId={LID}&season=2026&playerPool=all&limit=2000` → `{stats: [{splits: [{player: {id, fullName, firstName, lastName}, team: {...}, stat: {...}}]}]}`. CCBL live counts: 205 hitters / 251 pitchers. Hitting stat keys incl. `gamesPlayed, plateAppearances, atBats, runs, hits, doubles, triples, homeRuns, rbi, baseOnBalls, strikeOuts, hitByPitch, stolenBases, caughtStealing, sacFlies, sacBunts`. Pitching incl. `gamesPlayed, gamesStarted, inningsPitched ("6.0" string), wins, losses, saves, holds, hits, runs, earnedRuns, baseOnBalls, strikeOuts, hitBatsmen, homeRuns, battersFaced`.
- Player game log: `GET https://statsapi.mlb.com/api/v1/people/{id}/stats?stats=gameLog&group=hitting,pitching&season=2026&sportId=22` → per-group stat objects with `splits[]`, each split: `{date (ISO), isHome, league: {id, name}, team, opponent: {name}, stat: {...}}`. **Splits span ALL sportId-22 leagues (college spring + summer)** — MUST filter `split.league.id == league_id`.
- Verified players: Jordan Lodise 838363 (Hyannis, 16 G, .262, 3 HR), Brady Fox 836190 (Orleans, 6 G, 6.0 IP, 11 K, 1 HLD).
- No auth, generous public API; keep the polite 1 rps throttle + UA header anyway.

---

## File structure

```
pipeline/scrapers/mlbstats.py           # NEW platform module (CCBL + Appalachian + future MLB-platform leagues)
pipeline/scrapers/__init__.py           # register "mlbstats"
pipeline/fixtures/mlbstats_ccbl/        # trimmed real captures (Task 1)
  hitting.json  pitching.json  gamelog_838363.json  gamelog_836190.json
pipeline/tests/test_mlbstats.py         # NEW (offline, monkeypatched)
pipeline/players.yaml                   # Task 1: resolved MLB person ids; Task 3 untouched
pipeline/leagues.yaml                   # Task 3: cape_cod + appalachian flip to mlbstats
```

All commands from the worktree root (quote paths — spaces). Current suite: 57 pytest / 19 vitest (post site-updates merge — re-verify the actual number at Task 1 start and use it as the baseline B; expectations below are stated relative to B).

---

### Task 1: Capture fixtures + resolve MLB person ids

**Files:**
- Create: `pipeline/fixtures/mlbstats_ccbl/{hitting,pitching,gamelog_838363,gamelog_836190}.json`
- Modify: `pipeline/players.yaml` (stats_ids only)

- [ ] **Step 1: Capture and trim league stats.**

```bash
mkdir -p pipeline/fixtures/mlbstats_ccbl
BASE="https://statsapi.mlb.com/api/v1"
curl -s "$BASE/stats?stats=season&group=hitting&sportId=22&leagueId=565&season=2026&playerPool=all&limit=2000" -o /tmp/ccbl_hit.json
curl -s "$BASE/stats?stats=season&group=pitching&sportId=22&leagueId=565&season=2026&playerPool=all&limit=2000" -o /tmp/ccbl_pit.json
curl -s "$BASE/people/838363/stats?stats=gameLog&group=hitting,pitching&season=2026&sportId=22" -o pipeline/fixtures/mlbstats_ccbl/gamelog_838363.json
curl -s "$BASE/people/836190/stats?stats=gameLog&group=hitting,pitching&season=2026&sportId=22" -o pipeline/fixtures/mlbstats_ccbl/gamelog_836190.json
.venv/bin/python - <<'EOF'
import json

GT_NAMES = {"Caleb Daniel", "Dimitri Angelakos", "Drew Rogers", "Adam McKelvey",
            "Tyler Guerin", "Holden Pantier", "Jordan Lodise", "Brady Fox"}

for kind, path in (("hitting", "/tmp/ccbl_hit.json"), ("pitching", "/tmp/ccbl_pit.json")):
    d = json.load(open(path))
    splits = d["stats"][0]["splits"]
    keep = [s for s in splits if s["player"]["fullName"] in GT_NAMES]
    keep += [s for s in splits if s["player"]["fullName"] not in GT_NAMES][:10]
    d["stats"][0]["splits"] = keep
    json.dump(d, open(f"pipeline/fixtures/mlbstats_ccbl/{kind}.json", "w"), indent=1)
    print(kind, "kept", len(keep), "GT matches:", [s["player"]["fullName"] for s in keep if s["player"]["fullName"] in GT_NAMES])
EOF
```
Report which GT names matched in each group. Verify both gamelog files parse and contain a `league` object with id 565 in at least one split.

- [ ] **Step 2: Resolve person ids for the placeholder players.** Run:

```bash
.venv/bin/python - <<'EOF'
import json
ids = {}
for kind in ("hitting", "pitching"):
    d = json.load(open(f"pipeline/fixtures/mlbstats_ccbl/{kind}.json"))
    for s in d["stats"][0]["splits"]:
        ids[s["player"]["fullName"]] = (s["player"]["id"], s.get("team", {}).get("name"))
for name in ("Caleb Daniel", "Dimitri Angelakos", "Drew Rogers", "Adam McKelvey",
             "Tyler Guerin", "Holden Pantier"):
    print(name, "->", ids.get(name, "NOT FOUND IN CCBL STATS"))
EOF
curl -s "https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting&sportId=22&leagueId=120&season=2026&playerPool=all&limit=2000" | .venv/bin/python -c "
import json, sys
d = json.load(sys.stdin)
hits = [s for s in d['stats'][0]['splits'] if s['player']['fullName'] == 'Judson Hartwell']
print('Judson Hartwell ->', [(s['player']['id'], s.get('team', {}).get('name')) for s in hits] or 'NOT FOUND IN APPY HITTING')
"
```

For every player found: update their `stats_id` in `pipeline/players.yaml` to the quoted numeric id (e.g. `stats_id: "841234"`). Cross-check the team name printed matches the registry's team (e.g. Pantier → Brewster Whitecaps; a mismatch means wrong person — skip and report). Players NOT found keep their slug placeholder (they'll warn at build, correctly — e.g. a player who hasn't appeared yet). Report the final id table and any not-found/mismatched players.

- [ ] **Step 3: Commit**

```bash
git add pipeline/fixtures/mlbstats_ccbl pipeline/players.yaml
git commit -m "test: MLB StatsAPI fixtures (CCBL); resolve person ids for CCBL/Appy players"
```

---

### Task 2: mlbstats scraper module

**Files:**
- Create: `pipeline/scrapers/mlbstats.py`
- Modify: `pipeline/scrapers/__init__.py`
- Test: `pipeline/tests/test_mlbstats.py`

- [ ] **Step 1: Write the failing tests** — `pipeline/tests/test_mlbstats.py`:

```python
import json
from pathlib import Path

from pipeline.scrapers import SCRAPERS, mlbstats

FIX = Path("pipeline/fixtures/mlbstats_ccbl")
CFG = {"api_base": "https://statsapi.example/api/v1", "sport_id": 22,
       "league_id": 565, "season": 2026}


def _fake_get_json(monkeypatch):
    def fake(url):
        if "group=hitting&sportId" in url and "/stats?" in url:
            return json.loads((FIX / "hitting.json").read_text())
        if "group=pitching&sportId" in url and "/stats?" in url:
            return json.loads((FIX / "pitching.json").read_text())
        for pid in ("838363", "836190"):
            if f"/people/{pid}/" in url:
                return json.loads((FIX / f"gamelog_{pid}.json").read_text())
        import requests
        resp = requests.Response()
        resp.status_code = 404
        raise requests.HTTPError(response=resp)
    monkeypatch.setattr(mlbstats, "_get_json", fake)
    monkeypatch.setattr(mlbstats.time, "sleep", lambda s: None)


def test_registered():
    assert SCRAPERS["mlbstats"] is mlbstats


def test_league_stats_normalized(monkeypatch):
    _fake_get_json(monkeypatch)
    stats = mlbstats.fetch_league_stats(CFG)
    bat_keys = {"stats_id", "name", "team", "g", "ab", "r", "h", "d", "t", "hr",
                "rbi", "bb", "k", "hbp", "sb", "cs", "sf", "sh", "pa"}
    pit_keys = {"stats_id", "name", "team", "g", "gs", "ip_outs", "w", "l", "sv",
                "hld", "h", "r", "er", "bb", "k", "hb", "hr", "bf"}
    assert set(stats["batting"][0]) == bat_keys
    assert set(stats["pitching"][0]) == pit_keys
    lodise = next(r for r in stats["batting"] if r["stats_id"] == "838363")
    assert lodise["name"] == "Jordan Lodise" and lodise["pa"] > 0
    fox = next(r for r in stats["pitching"] if r["stats_id"] == "836190")
    assert fox["hld"] >= 1 and fox["bf"] > 0 and isinstance(fox["ip_outs"], int)


def test_game_logs_filtered_to_league(monkeypatch):
    _fake_get_json(monkeypatch)
    logs = mlbstats.fetch_game_logs(CFG, ["838363", "836190", "some-slug", "999999999"])
    assert logs["some-slug"] == [] and logs["999999999"] == []
    lodise = logs["838363"]
    assert len(lodise) >= 5
    dates = [g["date"] for g in lodise]
    assert dates == sorted(dates, reverse=True)
    assert all(d.startswith("2026-") for d in dates)
    # THE critical assertion: college games (league != 565) are excluded
    raw = json.loads((FIX / "gamelog_838363.json").read_text())
    all_splits = [s for grp in raw["stats"] for s in grp.get("splits", [])]
    ccbl_splits = [s for s in all_splits if s.get("league", {}).get("id") == 565]
    assert len(all_splits) > len(ccbl_splits)          # fixture really contains college games
    assert len(lodise) == len(ccbl_splits)
    g = lodise[0]
    assert set(g) == {"date", "opponent", "ab", "r", "h", "d", "t", "hr", "rbi", "bb", "k", "sb"}
    assert g["opponent"].startswith(("vs ", "at "))
    fox = logs["836190"]
    assert fox and set(fox[0]) == {"date", "opponent", "ip_outs", "h", "r", "er", "bb", "k", "hr", "dec"}
    assert all(e["dec"] in ("W", "L", "SV", "") for e in fox)
```

- [ ] **Step 2:** Run `.venv/bin/pytest pipeline/tests/test_mlbstats.py -q` — expect ImportError.

- [ ] **Step 3: Implement** `pipeline/scrapers/mlbstats.py`:

```python
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
```

Register in `pipeline/scrapers/__init__.py`:
```python
"""Platform-name → scraper-module map."""
from pipeline.scrapers import fixture, mlbstats, scorebook

SCRAPERS = {"fixture": fixture, "mlbstats": mlbstats, "scorebook": scorebook}
```

- [ ] **Step 4:** `.venv/bin/pytest pipeline/tests/test_mlbstats.py -q` → `3 passed`; full suite → baseline B + 3.

- [ ] **Step 5: Commit**

```bash
git add pipeline/scrapers/mlbstats.py pipeline/scrapers/__init__.py pipeline/tests/test_mlbstats.py
git commit -m "feat: mlbstats platform scraper (Cape Cod + Appalachian via MLB StatsAPI)"
```

---

### Task 3: Flip the two leagues live

**Files:**
- Modify: `pipeline/leagues.yaml`
- Regenerate: `site/src/data/*`, `data/history/*`

- [ ] **Step 1:** In `pipeline/leagues.yaml`, change `cape_cod` and `appalachian` from `platform: pending` to:

```yaml
cape_cod:
  name: Cape Cod Baseball League
  abbrev: CCBL
  official_url: https://www.capecodleague.com
  platform: mlbstats
  api_base: https://statsapi.mlb.com/api/v1
  sport_id: 22
  league_id: 565
  season: 2026
  tier: 1
appalachian:
  name: Appalachian League
  abbrev: APPY
  official_url: https://www.appyleague.com
  platform: mlbstats
  api_base: https://statsapi.mlb.com/api/v1
  sport_id: 22
  league_id: 120
  season: 2026
  tier: 1
```
(`necbl`, `sfcbl`, `mlb_draft` stay pending.)

- [ ] **Step 2: Live rebuild.**

```bash
.venv/bin/python -m pipeline.build_data
```
Expected: 3 pending skips (mlb_draft, necbl, sfcbl), 0 failures, N warnings where N = number of CCBL/Appy players whose ids stayed placeholders in Task 1 (target 0 — report actual), summary `wrote 42 players; ...`, exit 0. Runtime ~15s (two leagues × 2 stat calls + up to 9 gamelog calls, throttled).

- [ ] **Step 3: Spot-check.**

```bash
.venv/bin/python -c "
import json
d = {p['slug']: p for p in json.load(open('site/src/data/players.json'))}
jl = d['jordan-lodise']
assert jl['hitting'] and len(jl['hitting']['sliders']) == 6
ks = {s['metric']: s for s in jl['hitting']['sliders']}
assert ks['kPct']['derived'] is False       # native PA from StatsAPI
bf = d['brady-fox']
assert bf['pitching'] and bf['pitching']['counting']['hld'] >= 1
jh = d['judson-hartwell']
print('Lodise:', jl['hitting']['counting']['g'], 'G; Fox HLD:', bf['pitching']['counting']['hld'],
      '; Hartwell:', 'LIVE' if jh['hitting'] or jh['pitching'] else 'awaiting (id unresolved?)')
"
ls site/src/data/gamelogs | wc -l
```

- [ ] **Step 4: Full verification.** `.venv/bin/pytest -q` (offline, baseline B + 3); `cd site && npx vitest run` (19) — NOTE: if a site data test pins specifics that changed (e.g. hitter counts), update minimally and report; `npm run build` (45 pages); `grep -c "Jordan Lodise" dist/index.html` ≥ 1 (now a live hitter row).

- [ ] **Step 5: Commit**

```bash
git add pipeline/leagues.yaml site/src/data data/history
git commit -m "feat!: Cape Cod + Appalachian leagues live via MLB StatsAPI"
```

---

## Self-review checklist (run after writing, fix inline)

1. **Spec coverage:** tier-1 full-pool percentiles for both leagues (205/251 pools confirmed live) ✓; polite scraping ✓; offline tests via monkeypatched `_get_json` ✓; college-game exclusion pinned by a fixture-backed assertion ✓; carry-forward/warning semantics inherited from build_data unchanged ✓; native PA/BF/HLD flow through Task 2's normalizers into the honest-derived-flag logic from Plan 3 ✓.
2. **Placeholder scan:** none — Task 1 prints resolved ids and the registry edit rule is explicit (found → quoted numeric id; not found → keep placeholder and report).
3. **Type consistency:** `SCRAPERS["mlbstats"]` ↔ `platform: mlbstats`; cfg keys (`api_base`, `sport_id`, `league_id`, `season`) consistent across scraper and leagues.yaml; canonical row keys identical to scorebook's contract; `ip_str_to_outs` reused; gamelog entry shapes match the site's `PitcherGame`/`HitterGame` types.
