import json
from pathlib import Path

from pipeline.scrapers import SCRAPERS, scorebook

FIX = Path("pipeline/fixtures/scorebook_nwl")
CFG = {"api_base": "https://scorebook.example/api"}


def _fake_get_json(monkeypatch):
    def fake(url):
        if url.endswith("/statistics/all/0?general=true"):
            return json.loads((FIX / "statistics_all.json").read_text())
        for pid in ("10225", "10352"):
            if url.endswith(f"/statistics/player/{pid}"):
                return json.loads((FIX / f"player_{pid}.json").read_text())
        import requests
        resp = requests.Response()
        resp.status_code = 404
        raise requests.HTTPError(response=resp)
    monkeypatch.setattr(scorebook, "_get_json", fake)
    monkeypatch.setattr(scorebook.time, "sleep", lambda s: None)


def test_registered():
    assert SCRAPERS["scorebook"] is scorebook


def test_league_stats_normalized(monkeypatch):
    _fake_get_json(monkeypatch)
    stats = scorebook.fetch_league_stats(CFG)
    assert len(stats["batting"]) == 12 and len(stats["pitching"]) == 12
    bat_keys = {"stats_id", "name", "team", "g", "ab", "r", "h", "d", "t", "hr",
                "rbi", "bb", "k", "hbp", "sb", "cs", "sf", "sh", "pa"}
    pit_keys = {"stats_id", "name", "team", "g", "gs", "ip_outs", "w", "l", "sv",
                "hld", "h", "r", "er", "bb", "k", "hb", "hr", "bf"}
    assert set(stats["batting"][0]) == bat_keys
    assert set(stats["pitching"][0]) == pit_keys
    riley = next(r for r in stats["pitching"] if r["stats_id"] == "10225")
    assert riley["name"] == "Riley Hasenstab"
    assert riley["team"] == "WIL"              # from team_abv (raw team field is a numeric id)
    assert riley["ip_outs"] == 97              # "32.1" -> 97 (fixture capture value)
    assert riley["bf"] == 138 and riley["hb"] == 2 and riley["hld"] == 0
    assert all(isinstance(r["stats_id"], str) for r in stats["pitching"])


def test_game_logs(monkeypatch):
    _fake_get_json(monkeypatch)
    logs = scorebook.fetch_game_logs(CFG, ["10225", "jackson-blakely", "99999999"])
    assert logs["jackson-blakely"] == []       # non-numeric placeholder id
    assert logs["99999999"] == []              # 404 -> empty
    riley = logs["10225"]
    assert len(riley) == 8
    dates = [g["date"] for g in riley]
    assert dates == sorted(dates, reverse=True)          # newest first
    assert all(d.startswith("2026-") and len(d) == 10 for d in dates)
    g = riley[0]
    assert set(g) == {"date", "opponent", "ip_outs", "h", "r", "er", "bb", "k", "hr", "dec"}
    assert g["date"] == "2026-07-13"
    assert g["opponent"] == "at Bismarck Larks"          # Willmar was the visitor
    assert g["dec"] == "W"
    assert g["ip_outs"] == 15                            # "5.0" IP that game
