from pipeline.scrapers import SCRAPERS
from pipeline.scrapers import fixture

CFG = {"fixture_dir": "pipeline/fixtures/northwoods_sample"}


def test_registered():
    assert SCRAPERS["fixture"] is fixture


def test_fetch_league_stats():
    stats = fixture.fetch_league_stats(CFG)
    pit_ids = {r["stats_id"] for r in stats["pitching"]}
    assert {"jackson-blakely", "jamie-vicens", "riley-hasenstab"} <= pit_ids
    assert len(stats["batting"]) >= 6 and len(stats["pitching"]) >= 8


def test_fetch_game_logs():
    logs = fixture.fetch_game_logs(CFG, ["jackson-blakely", "missing-guy"])
    assert len(logs["jackson-blakely"]) >= 2
    assert logs["missing-guy"] == []
