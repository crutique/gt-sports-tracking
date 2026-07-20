import gzip
import json
from pathlib import Path

from pipeline.scrapers import SCRAPERS, iscore

FIX = Path("pipeline/fixtures/iscore_sfcbl")
CFG = {"name": "South Florida Collegiate Baseball League", "abbrev": "SFCBL",
       "official_url": "https://sfcbl.com", "platform": "iscore",
       "api_base": "https://iscore.example/api",
       "league_id": "541ef447-c3d8-497d-811e-54bf6d5d9478",
       "season_id": "1a8ebd76-1702-4d2e-af70-88ad3a3a9040",
       "season": 2026, "tier": 1}

TEAM_BRB = "bb3f63a5-332e-4081-b21c-0195b6cf430a"     # Boca Raton Blazers
TEAM_WBS = "4374ad7b-ddf7-4f56-9f39-c57ff9b4800d"     # West Boca Snappers
COUPET = "5d32db3a-b7f8-4152-89cc-7a57ee42f972"
BLAXBERG = "4df1a50c-11ff-4a0e-ae77-24a4646ab7b7"     # two-way (batted + pitched)
KNIERIM = "a94774dd-3fe7-4c82-8202-86ca3c8ef757"      # two-way (PA 78, SV 2)
MAY = "f7274e07-35ca-4cb6-bcd6-fc5e39fa5eb7"          # empty stats {} — no appearances
REYES = "8b4d4005-cd1f-4572-8beb-6c982f0cb2dc"        # WBS batter
HOLLOWAY = "ec108020-0753-4b9b-a539-ed2d91b1c514"     # WBS pitcher
W_PITCH = "e8112049-e60a-4dc8-bace-91bae84176e4"      # winning pitcher, Jul 11 box
L_PITCH = "7a164050-5bed-4021-8117-4edde829ecd1"      # losing pitcher, Jul 13 box
NO_GAMES = "00000000-0000-4000-8000-000000000000"     # valid GUID, no games
NOT_FOUND = "99999999-9999-4999-8999-999999999999"    # valid GUID, API 404s

GAME_JUL13 = "7c0cd4a8-45bd-4356-a6f3-2a6b194ff492"
GAME_JUL11 = "f8d49810-df46-425e-b6fb-1e9d25590978"


def _fake_http(monkeypatch):
    def fake_json(url):
        if url.endswith(f"/public/leagues/{CFG['league_id']}/teams"):
            return json.loads((FIX / "teams.json").read_text())
        for tid in (TEAM_BRB, TEAM_WBS):
            if f"player-stats?teamId={tid}" in url:
                return json.loads((FIX / f"player_stats_{tid[:8]}.json").read_text())
        if "/public/games?" in url:
            games = json.loads((FIX / "games_5d32db3a.json").read_text())
            if f"playerId={COUPET}" in url or f"playerId={L_PITCH}" in url:
                return games
            if f"playerId={W_PITCH}" in url:
                return [g for g in games if g["gameGuid"] == GAME_JUL11]
            if f"playerId={NO_GAMES}" in url:
                return []
        import requests
        resp = requests.Response()
        resp.status_code = 404
        raise requests.HTTPError(response=resp)

    def fake_bytes(url):
        for guid in (GAME_JUL13, GAME_JUL11):
            if url.endswith(f"/public/games/{guid}/boxScore/gzip"):
                return gzip.compress((FIX / f"boxscore_{guid[:8]}.json").read_bytes())
        import requests
        resp = requests.Response()
        resp.status_code = 404
        raise requests.HTTPError(response=resp)

    monkeypatch.setattr(iscore, "_get_json", fake_json)
    monkeypatch.setattr(iscore, "_get_bytes", fake_bytes)
    monkeypatch.setattr(iscore.time, "sleep", lambda s: None)


def test_registered():
    assert SCRAPERS["iscore"] is iscore


def test_gunzip_json():
    assert iscore._gunzip_json(gzip.compress(b'{"a": 1}')) == {"a": 1}
    assert iscore._gunzip_json(b'{"a": 1}') == {"a": 1}   # tolerate plain JSON


def test_league_stats_normalized(monkeypatch):
    _fake_http(monkeypatch)
    stats = iscore.fetch_league_stats(CFG)
    bat_keys = {"stats_id", "name", "team", "g", "ab", "r", "h", "d", "t", "hr",
                "rbi", "bb", "k", "hbp", "sb", "cs", "sf", "sh", "pa"}
    pit_keys = {"stats_id", "name", "team", "g", "gs", "ip_outs", "w", "l", "sv",
                "hld", "h", "r", "er", "bb", "k", "hb", "hr", "bf"}
    assert all(set(r) == bat_keys for r in stats["batting"])
    assert all(set(r) == pit_keys for r in stats["pitching"])
    assert all(isinstance(r["stats_id"], str) for r in stats["batting"] + stats["pitching"])

    # pool assembly: anyone with PA/AB bats, anyone with BF/outs pitches; two-way in both
    assert {r["stats_id"] for r in stats["batting"]} == {COUPET, BLAXBERG, KNIERIM, REYES}
    assert {r["stats_id"] for r in stats["pitching"]} == {BLAXBERG, KNIERIM, HOLLOWAY}
    # Coupet has a pitching GP=1 with 0 BF and 0 outs -> NOT in the pitching pool
    # Carson May has stats: {} -> in neither pool

    coupet = next(r for r in stats["batting"] if r["stats_id"] == COUPET)
    assert coupet == {
        "stats_id": COUPET, "name": "Nathanael Coupet", "team": "Boca Raton Blazers",
        "g": 26, "ab": 89, "r": 15, "h": 26, "d": 8, "t": 0, "hr": 3, "rbi": 18,
        "bb": 9, "k": 18, "hbp": 3, "sb": 4, "cs": 2, "sf": 2, "sh": 0, "pa": 103,
    }
    knierim = next(r for r in stats["batting"] if r["stats_id"] == KNIERIM)
    assert knierim["pa"] == 78 and knierim["ab"] == 60      # native PA, not derived
    assert knierim["sb"] == 23 and knierim["cs"] == 0       # SB/CS come from stats.running

    holloway = next(r for r in stats["pitching"] if r["stats_id"] == HOLLOWAY)
    assert holloway["team"] == "West Boca Snappers"
    assert holloway["ip_outs"] == 69                        # native OUTS_PITCHED, no IP parsing
    assert isinstance(holloway["ip_outs"], int)
    assert holloway["bf"] == 123 and holloway["hb"] == 8    # native BF; HBP -> hb
    knierim_p = next(r for r in stats["pitching"] if r["stats_id"] == KNIERIM)
    assert knierim_p["sv"] == 2 and knierim_p["hld"] == 0 and knierim_p["er"] == 9


def test_game_logs(monkeypatch):
    _fake_http(monkeypatch)
    logs = iscore.fetch_game_logs(
        CFG, [COUPET, W_PITCH, L_PITCH, "nathanael-coupet", NO_GAMES, NOT_FOUND])
    assert logs["nathanael-coupet"] == []   # non-GUID placeholder id -> no HTTP
    assert logs[NO_GAMES] == []             # no games returned -> empty log
    assert logs[NOT_FOUND] == []            # 404 -> empty log, never raises

    # THE critical assertion: scheduled games (gameStatusId != 3) are excluded
    raw = json.loads((FIX / "games_5d32db3a.json").read_text())
    played = [g for g in raw if g["gameStatusId"] == 3]
    assert len(raw) > len(played)           # fixture really contains a scheduled game
    coupet = logs[COUPET]
    assert len(coupet) == len(played) == 2
    dates = [g["date"] for g in coupet]
    assert dates == sorted(dates, reverse=True)             # newest first
    assert coupet[0] == {"date": "2026-07-13", "opponent": "vs West Boca Snappers",
                         "ab": 5, "r": 1, "h": 1, "d": 0, "t": 0, "hr": 1,
                         "rbi": 3, "bb": 0, "k": 1, "sb": 0}
    assert coupet[1] == {"date": "2026-07-11", "opponent": "at West Boca Snappers",
                         "ab": 3, "r": 0, "h": 0, "d": 0, "t": 0, "hr": 0,
                         "rbi": 0, "bb": 0, "k": 1, "sb": 0}

    assert logs[W_PITCH] == [{"date": "2026-07-11", "opponent": "vs Boca Raton Blazers",
                              "ip_outs": 15, "h": 3, "r": 0, "er": 0, "bb": 1,
                              "k": 8, "hr": 0, "dec": "W"}]
    # L_PITCH's games list spans both games, but he only appears in the Jul 13
    # box score -> games without a stat line for the player are skipped
    assert logs[L_PITCH] == [{"date": "2026-07-13", "opponent": "at Boca Raton Blazers",
                              "ip_outs": 7, "h": 4, "r": 6, "er": 6, "bb": 6,
                              "k": 1, "hr": 1, "dec": "L"}]


def test_broken_hit_type_splits_derive_doubles_from_tb():
    # iScore regression seen 2026-07-20: 1B/2B/3B zero out while H/HR/TB stay right.
    p = {"playerId": "x", "firstName": "N", "lastName": "C",
         "stats": {"batting": {"overall": {"GP": 28, "PA": 111, "AB": 96, "H": 28,
                   "1B": 0, "2B": 0, "3B": 0, "HR": 4, "TB": 48, "R": 16, "RBI": 21,
                   "BB": 10, "SO": 18, "HBP": 3, "SF": 2, "SH": 0}}}}
    row = iscore._norm_bat(p, "T")
    assert row["d"] == 8 and row["t"] == 0 and row["h"] == 28


def test_healthy_hit_type_splits_untouched():
    p = {"playerId": "x", "firstName": "N", "lastName": "C",
         "stats": {"batting": {"overall": {"GP": 26, "PA": 103, "AB": 89, "H": 26,
                   "1B": 15, "2B": 8, "3B": 0, "HR": 3, "TB": 43, "R": 15, "RBI": 18,
                   "BB": 9, "SO": 18, "HBP": 3, "SF": 2, "SH": 0}}}}
    assert iscore._norm_bat(p, "T")["d"] == 8


def test_broken_splits_without_tb_keep_components():
    p = {"playerId": "x", "firstName": "N", "lastName": "C",
         "stats": {"batting": {"overall": {"GP": 5, "PA": 20, "AB": 18, "H": 6,
                   "1B": 0, "2B": 0, "3B": 0, "HR": 1}}}}
    assert iscore._norm_bat(p, "T")["d"] == 0
