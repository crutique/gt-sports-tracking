import pytest
from pipeline import registry


def test_load_all_seed_files():
    players, leagues = registry.load_all("pipeline/players.yaml", "pipeline/leagues.yaml")
    assert len(players) == 42
    slugs = [p["slug"] for p in players]
    assert len(slugs) == len(set(slugs))
    assigned = [p for p in players if p["summer"]["status"] == "assigned"]
    assert {p["slug"] for p in assigned} == {
        "jackson-blakely", "jamie-vicens", "riley-hasenstab", "caden-spivey",
    }
    assert "northwoods" in leagues and leagues["northwoods"]["tier"] == 1


def test_duplicate_slug_rejected(tmp_path):
    p = tmp_path / "players.yaml"
    p.write_text(
        "- {name: A, slug: dup, gt_status: returning, player_type: hitter, summer: {status: unassigned}}\n"
        "- {name: B, slug: dup, gt_status: freshman, summer: {status: unassigned}}\n"
    )
    l = tmp_path / "leagues.yaml"
    l.write_text("{}")
    with pytest.raises(registry.RegistryError, match="duplicate slug"):
        registry.load_all(str(p), str(l))


def test_assigned_requires_known_league_and_player_type(tmp_path):
    p = tmp_path / "players.yaml"
    p.write_text(
        "- {name: A, slug: a, gt_status: returning, player_type: pitcher,"
        " summer: {status: assigned, team: T, league: nope, stats_id: x}}\n"
    )
    l = tmp_path / "leagues.yaml"
    l.write_text("{}")
    with pytest.raises(registry.RegistryError, match="unknown league"):
        registry.load_all(str(p), str(l))


VALID_LEAGUE = "lg: {name: L, abbrev: LG, official_url: u, platform: pending, tier: 1}\n"


def test_duplicate_stats_id_in_league_rejected(tmp_path):
    p = tmp_path / "players.yaml"
    p.write_text(
        "- {name: A, slug: a, gt_status: returning, player_type: pitcher,"
        " summer: {status: assigned, team: T, league: lg, stats_id: same}}\n"
        "- {name: B, slug: b, gt_status: returning, player_type: hitter,"
        " summer: {status: assigned, team: U, league: lg, stats_id: same}}\n"
    )
    l = tmp_path / "leagues.yaml"
    l.write_text(VALID_LEAGUE)
    with pytest.raises(registry.RegistryError, match="duplicate stats_id"):
        registry.load_all(str(p), str(l))


def test_league_missing_required_key_rejected(tmp_path):
    p = tmp_path / "players.yaml"
    p.write_text("[]")
    l = tmp_path / "leagues.yaml"
    l.write_text("lg: {name: L, abbrev: LG, official_url: u, platform: pending}\n")
    with pytest.raises(registry.RegistryError, match="league tier missing"):
        registry.load_all(str(p), str(l))
    l.write_text("lg: {name: L, abbrev: LG, official_url: u, platform: fixture, tier: 1}\n")
    with pytest.raises(registry.RegistryError, match="league fixture_dir missing"):
        registry.load_all(str(p), str(l))


def test_assigned_missing_player_type_rejected(tmp_path):
    p = tmp_path / "players.yaml"
    p.write_text(
        "- {name: A, slug: a, gt_status: transfer,"
        " summer: {status: assigned, team: T, league: lg, stats_id: x}}\n"
    )
    l = tmp_path / "leagues.yaml"
    l.write_text(VALID_LEAGUE)
    with pytest.raises(registry.RegistryError, match="needs player_type"):
        registry.load_all(str(p), str(l))


def test_assigned_missing_team_or_stats_id_rejected(tmp_path):
    p = tmp_path / "players.yaml"
    p.write_text(
        "- {name: A, slug: a, gt_status: returning, player_type: pitcher,"
        " summer: {status: assigned, league: lg, stats_id: x}}\n"
    )
    l = tmp_path / "leagues.yaml"
    l.write_text(VALID_LEAGUE)
    with pytest.raises(registry.RegistryError, match="needs team and stats_id"):
        registry.load_all(str(p), str(l))
