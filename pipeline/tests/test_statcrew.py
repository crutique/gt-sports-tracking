"""StatCrew ``bsgame`` XML -- the canonical scorer output.

Every other feed we use (ncaa.com, ESPN, school and conference sites) is a
rendering *derived* from this file, so reading it directly removes the narrative
guesswork in :mod:`pipeline.ncaa_pbp` and supplies the fields the JSON feeds drop:
HBP/SF/SH, batter strikeouts, base-out state and handedness.

Fixture is a real archived game -- UC Davis at Texas, 2026-02-15 -- chosen because
ncaa.com's gamecenter and ESPN both have **no** play-by-play for it.
"""
from pathlib import Path

import pytest

from pipeline import statcrew

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "statcrew" / \
    "ucdavis_at_texas_2026-02-15.xml"


@pytest.fixture(scope="module")
def game():
    return statcrew.parse_game(FIXTURE.read_text(encoding="utf-8", errors="ignore"))


# --- game identity ----------------------------------------------------------
def test_reads_venue_and_date(game):
    assert game["date"] == "2026-02-15"
    assert game["stadium"] == "Disch-Falk Field"
    assert game["sbid"] == "651570"
    assert game["complete"] is True


def test_teams_are_identified_home_and_away(game):
    away, home = game["away"], game["home"]
    assert (away["name"], home["name"]) == ("UC Davis", "Texas")
    assert (away["runs"], home["runs"]) == (1, 9)


# --- the fields the JSON feeds cannot give ----------------------------------
def test_hbp_sf_sh_are_read_as_fields_not_parsed_from_prose(game):
    home = game["home"]["totals"]["batting"]      # Texas: hbp=1 sh=1 sf=2 sb=3
    assert (home["hbp"], home["sh"], home["sf"], home["sb"]) == (1, 1, 2, 3)
    away = game["away"]["totals"]["batting"]      # UC Davis: hbp=1 sh=1, no sf
    assert (away["hbp"], away["sh"]) == (1, 1)
    assert away["sf"] == 0, "an omitted attribute is a zero, not a missing key"


def test_batter_strikeouts_are_populated(game):
    # NCAA's JSON feed never fills batter K -- 0 of 395 real rows in a 2025 sample.
    # The XML does, so K% becomes computable.
    assert game["away"]["totals"]["batting"]["k"] == 10
    assert game["home"]["totals"]["batting"]["k"] == 7


def test_absent_attribute_means_zero_not_missing(game):
    # StatCrew omits any stat that is zero, so every canonical key must still exist
    for team in (game["away"], game["home"]):
        for p in team["players"]:
            for key in ("ab", "r", "h", "d", "t", "hr", "rbi", "bb", "k",
                        "hbp", "sf", "sh", "sb", "cs"):
                assert key in p["batting"], f"{p['name']} missing {key}"
                assert isinstance(p["batting"][key], int)


def test_player_lines_reconcile_to_the_files_own_totals(game):
    """The document carries its own <totals>, so summing the players is a real
    check on the reader rather than a restatement of it."""
    for team in (game["away"], game["home"]):
        tot = team["totals"]["batting"]
        for key in ("ab", "r", "h", "bb", "k", "hbp", "sf", "sh", "sb", "d", "rbi"):
            summed = sum(p["batting"][key] for p in team["players"])
            assert summed == tot[key], f"{team['name']} {key}: {summed} != {tot[key]}"


# --- identity comes free, no surname guessing -------------------------------
def test_players_carry_full_identity(game):
    p = next(x for x in game["away"]["players"] if x["name"] == "Braydon Wooldridge")
    assert (p["uni"], p["bats"], p["throws"], p["cls"]) == ("27", "L", "L", "SR")
    assert p["pos"] == "dh/p"


# --- pitching ---------------------------------------------------------------
def test_innings_pitched_convert_to_outs(game):
    # StatCrew writes IP as innings.outs -- "0.2" is two outs, not two-tenths
    assert statcrew.ip_to_outs("8.0") == 24
    assert statcrew.ip_to_outs("0.2") == 2
    assert statcrew.ip_to_outs("1.1") == 4
    assert statcrew.ip_to_outs("") == 0


def test_pitching_lines_use_canonical_keys(game):
    starter = next(p for p in game["home"]["players"]
                   if p["pitching"] and p["pitching"]["gs"] == 1)
    pit = starter["pitching"]
    for key in ("ip_outs", "h", "r", "er", "bb", "k", "hb", "bf"):
        assert key in pit
    assert pit["ip_outs"] > 0


# --- plays: structured state, not prose -------------------------------------
def test_plays_carry_base_out_state(game):
    plays = game["plays"]
    assert len(plays) == 105
    p = next(x for x in plays if x["seq"] == 9)
    assert p["outs"] == 2
    assert p["bases"] == {"first": "Borba", "second": "Tinney", "third": "Mendoza"}
    assert (p["batter"], p["batterHand"]) == ("Livingston", "L")
    assert (p["pitcher"], p["pitcherHand"]) == ("Speights", "R")
    assert (p["inning"], p["half"], p["teamId"]) == (1, "H", "TX")


def test_pitch_sequence_is_decoded_from_the_narrative(game):
    p = next(x for x in game["plays"] if x["seq"] == 9)
    assert p["pitches"] == "KBBSFFS"
    assert p["count"] == {"balls": 2, "strikes": 2}


def test_play_without_a_count_still_parses(game):
    # sac bunts and fielder's-choice plays often read "(0-0)" or carry no count
    for p in game["plays"]:
        assert "count" in p and "pitches" in p


def test_narrative_text_is_preserved_verbatim(game):
    p = next(x for x in game["plays"] if x["seq"] == 9)
    assert p["text"] == "Livingston struck out swinging (2-2 KBBSFFS)."


# --- the game this fixture was chosen for -----------------------------------
def test_recovers_a_game_the_json_feeds_lost(game):
    """ncaa.com returns 0 plays and ESPN renders "No plays available" for this
    contest; the XML has the whole thing."""
    texts = [p["text"] for p in game["plays"]]
    assert any("Hirschkorn struck out looking (3-2 BFKFFBBK)" in t for t in texts)
    assert sum(p["batting"]["hbp"] for p in game["away"]["players"]) == 1
