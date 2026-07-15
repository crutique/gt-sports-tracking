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
