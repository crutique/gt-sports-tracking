import json
import shutil
from pathlib import Path

import pytest

from pipeline import build_data

LEAGUES_TEMPLATE = (
    "northwoods:\n  name: Northwoods League\n  abbrev: NWL\n"
    "  official_url: https://northwoodsleague.com\n  platform: fixture\n"
    "  tier: 1\n  fixture_dir: {fixture_dir}\n"
    "mlb_draft:\n  name: MLB Draft League\n  abbrev: MLBDL\n"
    "  official_url: https://www.mlbdraftleague.com\n  platform: pending\n  tier: null\n")

PLAYERS_YAML = (
    "- {name: Jackson Blakely, slug: jackson-blakely, gt_status: returning, player_type: pitcher, position: P,"
    " summer: {status: assigned, team: Willmar Stingers, league: northwoods, stats_id: jackson-blakely}}\n"
    "- {name: Jamie Vicens, slug: jamie-vicens, gt_status: returning, player_type: pitcher, position: P,"
    " summer: {status: assigned, team: Willmar Stingers, league: northwoods, stats_id: jamie-vicens}}\n"
    "- {name: Riley Hasenstab, slug: riley-hasenstab, gt_status: returning, player_type: pitcher, position: P,"
    " summer: {status: assigned, team: Willmar Stingers, league: northwoods, stats_id: riley-hasenstab}}\n"
    "- {name: Caden Spivey, slug: caden-spivey, gt_status: returning, player_type: pitcher, position: P,"
    " summer: {status: assigned, team: Trenton Thunder, league: mlb_draft, stats_id: caden-spivey}}\n"
    "- {name: Will Baker, slug: will-baker, gt_status: returning, player_type: hitter, position: \"\","
    " summer: {status: unassigned}}\n")


def _copy_fixture(tmp_path):
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir(exist_ok=True)
    src = Path("pipeline/fixtures/northwoods_sample")
    for name in ("batting.json", "pitching.json", "gamelogs.json"):
        shutil.copy(src / name, fixture_dir / name)
    return fixture_dir


def _setup(tmp_path, fixture_dir=None):
    fixture_dir = fixture_dir or _copy_fixture(tmp_path)
    players = tmp_path / "players.yaml"
    players.write_text(PLAYERS_YAML)
    leagues = tmp_path / "leagues.yaml"
    leagues.write_text(LEAGUES_TEMPLATE.format(fixture_dir=fixture_dir))
    return str(players), str(leagues), fixture_dir


def test_full_build_happy_path(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    players, leagues, _ = _setup(tmp_path)
    result = build_data.build(players, leagues, out, hist, today="2026-07-14")
    assert result.failures == []
    assert "mlb_draft" in result.skipped
    recs = {r["slug"]: r for r in json.loads((out / "players.json").read_text())}
    assert len(recs) == 5
    jb = recs["jackson-blakely"]
    assert jb["asOf"] == "2026-07-14"
    metrics = [s["metric"] for s in jb["pitching"]["sliders"]]
    assert metrics == ["era", "whip", "kPct", "bbPct", "hr9", "oppAvg"]
    assert recs["caden-spivey"]["pitching"] is None
    assert recs["will-baker"]["summer"]["status"] == "unassigned"
    log = json.loads((out / "gamelogs" / "jackson-blakely.json").read_text())
    assert log[0]["date"] >= log[-1]["date"]


def test_failed_league_carries_forward(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    players, leagues_ok, _ = _setup(tmp_path)
    build_data.build(players, leagues_ok, out, hist, today="2026-07-14")
    log_path = out / "gamelogs" / "jackson-blakely.json"
    log_before = log_path.read_text()
    broken = tmp_path / "leagues_broken.yaml"
    broken.write_text(LEAGUES_TEMPLATE.format(fixture_dir="/nonexistent"))
    result = build_data.build(players, str(broken), out, hist, today="2026-07-15")
    assert [f[0] for f in result.failures] == ["northwoods"]
    recs = {r["slug"]: r for r in json.loads((out / "players.json").read_text())}
    jb = recs["jackson-blakely"]
    assert jb["asOf"] == "2026-07-14"
    assert jb["pitching"]["counting"]["g"] == 7
    assert log_path.read_text() == log_before
    assert (hist / "2026-07-15" / "gamelogs" / "jackson-blakely.json").exists()


def test_validation_error_fails_league(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    fixture_dir = _copy_fixture(tmp_path)
    batting = json.loads((fixture_dir / "batting.json").read_text())
    batting[0]["h"] = batting[0]["ab"] + 10
    (fixture_dir / "batting.json").write_text(json.dumps(batting))
    players, leagues, _ = _setup(tmp_path, fixture_dir=fixture_dir)
    result = build_data.build(players, leagues, out, hist, today="2026-07-14")
    assert len(result.failures) == 1 and result.failures[0][0] == "northwoods"
    assert "impossible" in result.failures[0][1]


def test_missing_player_keeps_gamelog_in_healthy_league(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    players, leagues_ok, _ = _setup(tmp_path)
    build_data.build(players, leagues_ok, out, hist, today="2026-07-14")
    log_path = out / "gamelogs" / "jackson-blakely.json"
    log_before = log_path.read_text()
    fixture_dir = tmp_path / "fixture2"
    fixture_dir.mkdir()
    src = Path("pipeline/fixtures/northwoods_sample")
    for name in ("batting.json", "pitching.json", "gamelogs.json"):
        shutil.copy(src / name, fixture_dir / name)
    pitching = json.loads((fixture_dir / "pitching.json").read_text())
    pitching = [r for r in pitching if r["stats_id"] != "jackson-blakely"]
    (fixture_dir / "pitching.json").write_text(json.dumps(pitching))
    leagues2 = tmp_path / "leagues2.yaml"
    leagues2.write_text(LEAGUES_TEMPLATE.format(fixture_dir=fixture_dir))
    result = build_data.build(players, str(leagues2), out, hist, today="2026-07-15")
    assert result.failures == []
    assert any("jackson-blakely" in w for w in result.warnings)
    recs = {r["slug"]: r for r in json.loads((out / "players.json").read_text())}
    assert recs["jackson-blakely"]["asOf"] == "2026-07-14"
    assert log_path.read_text() == log_before


def test_player_missing_from_stats_and_gamelogs_keeps_gamelog(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    players, leagues_ok, _ = _setup(tmp_path)
    build_data.build(players, leagues_ok, out, hist, today="2026-07-14")
    log_path = out / "gamelogs" / "jackson-blakely.json"
    log_before = log_path.read_text()
    fixture_dir = tmp_path / "fixture3"
    fixture_dir.mkdir()
    src = Path("pipeline/fixtures/northwoods_sample")
    for name in ("batting.json", "pitching.json", "gamelogs.json"):
        shutil.copy(src / name, fixture_dir / name)
    pitching = json.loads((fixture_dir / "pitching.json").read_text())
    pitching = [r for r in pitching if r["stats_id"] != "jackson-blakely"]
    (fixture_dir / "pitching.json").write_text(json.dumps(pitching))
    gamelogs = json.loads((fixture_dir / "gamelogs.json").read_text())
    gamelogs.pop("jackson-blakely")
    (fixture_dir / "gamelogs.json").write_text(json.dumps(gamelogs))
    leagues3 = tmp_path / "leagues3.yaml"
    leagues3.write_text(LEAGUES_TEMPLATE.format(fixture_dir=fixture_dir))
    result = build_data.build(players, str(leagues3), out, hist, today="2026-07-15")
    assert result.failures == []
    assert log_path.read_text() == log_before


def test_name_watch_warning_surfaces_in_build(tmp_path, capsys):
    # "Sample Slugger" sits in the fetched northwoods batting pool; a registry
    # player with that name is unassigned -> name-watch warning in result +
    # stdout, but the build itself stays healthy.
    out, hist = tmp_path / "data", tmp_path / "history"
    fixture_dir = _copy_fixture(tmp_path)
    players = tmp_path / "players.yaml"
    players.write_text(PLAYERS_YAML + (
        "- {name: Sample Slugger, slug: sample-slugger, gt_status: transfer,"
        " summer: {status: unassigned}}\n"))
    leagues = tmp_path / "leagues.yaml"
    leagues.write_text(LEAGUES_TEMPLATE.format(fixture_dir=fixture_dir))
    result = build_data.build(str(players), str(leagues), out, hist, today="2026-07-14")
    assert result.failures == []
    nw = [w for w in result.warnings if w.startswith("name-watch:")]
    assert len(nw) == 1
    assert "'Sample Slugger'" in nw[0]
    assert "northwoods batting row stats_id=fx-b1" in nw[0]
    assert any("WARNING name-watch:" in line
               for line in capsys.readouterr().out.splitlines())


def test_no_name_watch_warnings_when_assignments_match(tmp_path):
    # Every registry name in the pools is assigned with the matching stats_id.
    out, hist = tmp_path / "data", tmp_path / "history"
    players, leagues, _ = _setup(tmp_path)
    result = build_data.build(players, leagues, out, hist, today="2026-07-14")
    assert [w for w in result.warnings if w.startswith("name-watch:")] == []


def test_present_player_empty_log_fetch_keeps_existing_file(tmp_path):
    out, hist = tmp_path / "data", tmp_path / "history"
    players, leagues_ok, _ = _setup(tmp_path)
    build_data.build(players, leagues_ok, out, hist, today="2026-07-14")
    log_path = out / "gamelogs" / "jackson-blakely.json"
    log_before = log_path.read_text()
    fixture_dir = tmp_path / "fixture4"
    fixture_dir.mkdir()
    src = Path("pipeline/fixtures/northwoods_sample")
    for name in ("batting.json", "pitching.json", "gamelogs.json"):
        shutil.copy(src / name, fixture_dir / name)
    gamelogs = json.loads((fixture_dir / "gamelogs.json").read_text())
    gamelogs["jackson-blakely"] = []            # still in stats tables, log fetch empty
    (fixture_dir / "gamelogs.json").write_text(json.dumps(gamelogs))
    leagues4 = tmp_path / "leagues4.yaml"
    leagues4.write_text(LEAGUES_TEMPLATE.format(fixture_dir=fixture_dir))
    result = build_data.build(players, str(leagues4), out, hist, today="2026-07-15")
    assert result.failures == []
    recs = {r["slug"]: r for r in json.loads((out / "players.json").read_text())}
    assert recs["jackson-blakely"]["asOf"] == "2026-07-15"   # stats ARE fresh
    assert log_path.read_text() == log_before                # log file untouched


@pytest.fixture(autouse=True)
def _no_live_draft(request, monkeypatch, tmp_path):
    """Keep pre-existing build tests offline: default to a nonexistent draft path."""
    if "draft" in request.node.name:
        return    # draft-specific tests manage their own draft_path/mocks
    from pipeline import build_data as bd
    monkeypatch.setattr(bd, "DEFAULT_DRAFT_PATH", str(tmp_path / "absent-draft.yaml"))


def test_draft_json_written_and_isolated(tmp_path, monkeypatch, capsys):
    players, leagues, _ = _setup(tmp_path)
    draft_yaml = tmp_path / "draft.yaml"
    draft_yaml.write_text("- {name: A, person_id: 1, gt_role: departing}\n")
    from pipeline import draft_status
    monkeypatch.setattr(draft_status, "build_draft",
                        lambda entries, today, deadline=draft_status.DEADLINE:
                        {"asOf": today, "players": [], "udfa": []})
    result = build_data.build(players, leagues, str(tmp_path / "out"),
                              str(tmp_path / "hist"), today="2026-07-20",
                              draft_path=str(draft_yaml))
    assert (tmp_path / "out" / "draft.json").exists()
    assert not any(k == "draft" for k, _ in result.failures)


def test_draft_failure_keeps_previous_file(tmp_path, monkeypatch, capsys):
    players, leagues, _ = _setup(tmp_path)
    draft_yaml = tmp_path / "draft.yaml"
    draft_yaml.write_text("- {name: A, person_id: 1, gt_role: departing}\n")
    out = tmp_path / "out"
    out.mkdir()
    (out / "draft.json").write_text('{"asOf": "2026-07-19", "players": [], "udfa": []}')
    from pipeline import draft_status
    def boom(entries, today, deadline=draft_status.DEADLINE):
        raise RuntimeError("api down")
    monkeypatch.setattr(draft_status, "build_draft", boom)
    result = build_data.build(players, leagues, str(out),
                              str(tmp_path / "hist"), today="2026-07-20",
                              draft_path=str(draft_yaml))
    assert ("draft", "api down") in [(k, e) for k, e in result.failures]
    assert '"2026-07-19"' in (out / "draft.json").read_text()   # previous file untouched
    assert "FAILED draft" in capsys.readouterr().err


def test_missing_draft_yaml_is_not_an_error(tmp_path):
    players, leagues, _ = _setup(tmp_path)
    result = build_data.build(players, leagues, str(tmp_path / "out"),
                              str(tmp_path / "hist"), today="2026-07-20",
                              draft_path=str(tmp_path / "nope.yaml"))
    assert not any(k == "draft" for k, _ in result.failures)
