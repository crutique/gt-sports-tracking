import json
import shutil
from pathlib import Path

from pipeline import build_data

LEAGUES_TEMPLATE = (
    "northwoods:\n  name: Northwoods League\n  abbrev: NWL\n"
    "  official_url: https://northwoodsleague.com\n  platform: fixture\n"
    "  tier: 1\n  fixture_dir: {fixture_dir}\n"
    "mlb_draft:\n  name: MLB Draft League\n  abbrev: MLBDL\n"
    "  official_url: https://www.mlbdraftleague.com\n  platform: pending\n  tier: null\n")


def _copy_fixture(tmp_path):
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    src = Path("pipeline/fixtures/northwoods_sample")
    for name in ("batting.json", "pitching.json", "gamelogs.json"):
        shutil.copy(src / name, fixture_dir / name)
    return fixture_dir


def test_full_build_happy_path(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    result = build_data.build("pipeline/players.yaml", "pipeline/leagues.yaml",
                              out, hist, today="2026-07-14")
    assert result.failures == []
    assert "mlb_draft" in result.skipped            # platform: pending
    players = {r["slug"]: r for r in json.loads((out / "players.json").read_text())}
    assert len(players) == 42
    jb = players["jackson-blakely"]
    assert jb["asOf"] == "2026-07-14"
    metrics = [s["metric"] for s in jb["pitching"]["sliders"]]
    assert metrics == ["era", "whip", "kPct", "bbPct", "hr9", "oppAvg"]
    assert players["caden-spivey"]["pitching"] is None       # pending platform, no previous
    assert players["will-baker"]["summer"]["status"] == "unassigned"
    log = json.loads((out / "gamelogs" / "jackson-blakely.json").read_text())
    assert log[0]["date"] >= log[-1]["date"]                  # newest first


def test_failed_league_carries_forward(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    build_data.build("pipeline/players.yaml", "pipeline/leagues.yaml", out, hist,
                     today="2026-07-14")
    log_path = out / "gamelogs" / "jackson-blakely.json"
    log_before = log_path.read_text()
    # break the league: point fixture_dir somewhere empty
    leagues = tmp_path / "leagues.yaml"
    leagues.write_text(
        "northwoods:\n  name: Northwoods League\n  abbrev: NWL\n"
        "  official_url: https://northwoodsleague.com\n  platform: fixture\n"
        "  tier: 1\n  fixture_dir: /nonexistent\n"
        "mlb_draft:\n  name: MLB Draft League\n  abbrev: MLBDL\n"
        "  official_url: https://www.mlbdraftleague.com\n  platform: pending\n  tier: null\n")
    result = build_data.build("pipeline/players.yaml", str(leagues), out, hist,
                              today="2026-07-15")
    assert [f[0] for f in result.failures] == ["northwoods"]
    players = {r["slug"]: r for r in json.loads((out / "players.json").read_text())}
    jb = players["jackson-blakely"]
    assert jb["asOf"] == "2026-07-14"                 # yesterday's data survived
    assert jb["pitching"]["counting"]["g"] == 7
    assert log_path.read_text() == log_before        # stale-but-correct gamelog untouched
    assert (hist / "2026-07-15" / "gamelogs" / "jackson-blakely.json").exists()


def test_validation_error_fails_league(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    fixture_dir = _copy_fixture(tmp_path)
    batting = json.loads((fixture_dir / "batting.json").read_text())
    batting[0]["h"] = batting[0]["ab"] + 10        # impossible AVG > 1
    (fixture_dir / "batting.json").write_text(json.dumps(batting))
    leagues = tmp_path / "leagues.yaml"
    leagues.write_text(LEAGUES_TEMPLATE.format(fixture_dir=fixture_dir))
    result = build_data.build("pipeline/players.yaml", str(leagues), out, hist,
                              today="2026-07-14")
    assert len(result.failures) == 1 and result.failures[0][0] == "northwoods"
    assert "impossible" in result.failures[0][1]


def test_missing_player_keeps_gamelog_in_healthy_league(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    build_data.build("pipeline/players.yaml", "pipeline/leagues.yaml", out, hist,
                     today="2026-07-14")
    log_path = out / "gamelogs" / "jackson-blakely.json"
    log_before = log_path.read_text()
    fixture_dir = _copy_fixture(tmp_path)
    pitching = json.loads((fixture_dir / "pitching.json").read_text())
    pitching = [r for r in pitching if r["stats_id"] != "jackson-blakely"]
    (fixture_dir / "pitching.json").write_text(json.dumps(pitching))
    leagues = tmp_path / "leagues.yaml"
    leagues.write_text(LEAGUES_TEMPLATE.format(fixture_dir=fixture_dir))
    result = build_data.build("pipeline/players.yaml", str(leagues), out, hist,
                              today="2026-07-15")
    assert result.failures == []
    assert any("jackson-blakely" in w for w in result.warnings)
    players = {r["slug"]: r for r in json.loads((out / "players.json").read_text())}
    jb = players["jackson-blakely"]
    assert jb["asOf"] == "2026-07-14"              # stats carried forward
    assert jb["pitching"]["counting"]["g"] == 7
    assert log_path.read_text() == log_before      # gamelog NOT wiped


def test_player_missing_from_stats_and_gamelogs_keeps_gamelog(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    build_data.build("pipeline/players.yaml", "pipeline/leagues.yaml", out, hist,
                     today="2026-07-14")
    log_path = out / "gamelogs" / "jackson-blakely.json"
    log_before = log_path.read_text()
    fixture_dir = _copy_fixture(tmp_path)
    pitching = json.loads((fixture_dir / "pitching.json").read_text())
    pitching = [r for r in pitching if r["stats_id"] != "jackson-blakely"]
    (fixture_dir / "pitching.json").write_text(json.dumps(pitching))
    gamelogs = json.loads((fixture_dir / "gamelogs.json").read_text())
    gamelogs.pop("jackson-blakely")
    (fixture_dir / "gamelogs.json").write_text(json.dumps(gamelogs))
    leagues = tmp_path / "leagues.yaml"
    leagues.write_text(LEAGUES_TEMPLATE.format(fixture_dir=fixture_dir))
    result = build_data.build("pipeline/players.yaml", str(leagues), out, hist,
                              today="2026-07-15")
    assert result.failures == []
    assert log_path.read_text() == log_before      # the actual wipe-bug scenario
