"""Parser tests built from REAL play text mined off ncaa.com (24 games, 1822 plays)."""
import pytest

from pipeline import ncaa_pbp as pbp


# --- clause splitting -------------------------------------------------------
def test_splits_on_mangled_3a_delimiter():
    # `3a` (0x3a) is how the feed's clause separator arrives; it is NOT part of the play
    text = "FORD, H. singled to left field (1-2 BFK)3a CHAPMAN, R. advanced to second."
    # the count parenthetical is stripped too — it is never content
    assert pbp.split_clauses(text) == [
        "FORD, H. singled to left field", "CHAPMAN, R. advanced to second"]


def test_splits_on_semicolons_and_strips_counts():
    text = "BROWN, T. doubled down the lf line, RBI; SMITH, K. scored."
    assert pbp.split_clauses(text) == [
        "BROWN, T. doubled down the lf line, RBI", "SMITH, K. scored"]


def test_does_not_split_a_bare_3a_inside_a_word():
    assert pbp.split_clauses("Player x3abc singled") == ["Player x3abc singled"]


# --- event classification ---------------------------------------------------
@pytest.mark.parametrize("clause", [
    "Davis Hanson hit by pitch.",
    "Fralick, C. hit by pitch",
    "Perkins,Maalik hit by pitch.",
    "Z. Williams hit by pitch",
])
def test_classifies_hit_by_pitch(clause):
    assert pbp.classify(clause) == pbp.HBP


@pytest.mark.parametrize("clause", [
    "Parker flied out to lf, SF, RBI",                      # abbreviated
    "Ronan Donohue flied out to 3b, sacrifice fly, RBI",    # spelled out
    "Murphy,Preston sacrifice fly to left center putout by lf, RBI",  # leading form
])
def test_classifies_sacrifice_fly(clause):
    assert pbp.classify(clause) == pbp.SF


def test_classifies_sacrifice_bunt():
    assert pbp.classify("Garcia, L. sacrifice bunt, out at first p to 1b") == pbp.SH
    assert pbp.classify("Smith sacrificed to p, bunt") == pbp.SH


@pytest.mark.parametrize("clause", [
    "Rembert, C. struck out swinging (2-2 BFBSS)",
    "Carter, B. walked (3-1 FBBBB)",
    "Matt Bolton was intentionally walked.",   # a walk, NOT hbp/sf/sh
    "Carter, B. advanced to second on an error by p",
    "Seidel,Sam flied out to rf.",             # ordinary fly out, no SF
    "BSU pitching change: Burden,Alex replaces Johnson,Keegan",
])
def test_ignores_non_events(clause):
    assert pbp.classify(clause) is None


def test_sac_fly_requires_the_marker_not_just_a_flyout_with_rbi():
    # a fly out that scores a run is only an SF when the feed marks it as one
    assert pbp.classify("Carter, B. flied out to cf, RBI") is None


# --- name extraction + roster matching --------------------------------------
@pytest.mark.parametrize("clause,expected", [
    ("Fralick, C. hit by pitch.", "Fralick, C."),
    ("Murphy,Preston sacrifice fly to left center, RBI", "Murphy,Preston"),
    ("Davis Hanson hit by pitch.", "Davis Hanson"),
    ("Z. Williams hit by pitch", "Z. Williams"),
    ("Vercollone hit by pitch.", "Vercollone"),
])
def test_extracts_leading_name(clause, expected):
    assert pbp.leading_name(clause) == expected


ROSTER = [
    {"key": "p1", "firstName": "Connor", "lastName": "Fralick"},
    {"key": "p2", "firstName": "Preston", "lastName": "Murphy"},
    {"key": "p3", "firstName": "Davis", "lastName": "Hanson"},
    {"key": "p4", "firstName": "Zack", "lastName": "Williams"},
    {"key": "p5", "firstName": "Mike", "lastName": "Vercollone"},
    {"key": "p6", "firstName": "Adam", "lastName": "Williams"},   # same-surname foil
]


@pytest.mark.parametrize("name,expected", [
    ("Fralick, C.", "p1"),        # Last, Initial
    ("Murphy,Preston", "p2"),     # Last,First (no space)
    ("Davis Hanson", "p3"),       # First Last
    ("Vercollone", "p5"),         # bare surname, unique
    ("Z. Williams", "p4"),        # Initial. Last  -> disambiguates the two Williamses
])
def test_matches_roster(name, expected):
    assert pbp.match_player(name, ROSTER) == expected


def test_ambiguous_surname_is_left_unattributed():
    # bare "Williams" matches two players -> refuse to guess (no fabricated attribution)
    assert pbp.match_player("Williams", ROSTER) is None


def test_unknown_name_is_unattributed():
    assert pbp.match_player("Nobody, X.", ROSTER) is None


# --- whole-game aggregation -------------------------------------------------
def _pbp_payload():
    return {"periods": [
        {"periodNumber": 1, "playbyplayStats": [
            {"teamId": 10, "plays": [
                {"playText": "Fralick, C. hit by pitch (1-0 B)"},
                {"playText": "Murphy,Preston sacrifice fly to left center, RBI3a "
                             "Fralick, C. scored."},
            ]},
            {"teamId": 20, "plays": [
                {"playText": "Davis Hanson hit by pitch."},
                {"playText": "Some Guy struck out swinging (2-2 KFBSS)"},
            ]},
        ]},
    ]}


def test_game_events_attributes_by_batting_team():
    rosters = {10: ROSTER, 20: ROSTER}
    ev = pbp.game_events(_pbp_payload(), rosters)
    assert ev[10]["p1"][pbp.HBP] == 1
    assert ev[10]["p2"][pbp.SF] == 1
    assert ev[20]["p3"][pbp.HBP] == 1
    # the batter's own HBP is credited once, and the later "scored" clause adds nothing
    assert sum(c[pbp.HBP] for c in ev[10].values()) == 1


def test_game_events_skips_teams_without_a_roster():
    ev = pbp.game_events(_pbp_payload(), {10: ROSTER})
    assert 20 not in ev or not ev[20]


# --- identity normalization -------------------------------------------------
# Real quirk: ~1 game in 12 arrives with firstName empty and the FULL name packed
# into lastName. Left alone it mints a second identity for the same player (which
# silently split one player's season across two keys during validation).
def test_roster_normalizes_full_name_packed_into_lastname():
    team_box = {"playerStats": [
        {"firstName": "", "lastName": "Vahn Lackey", "batterStats": {"atBats": "3"}},
        {"firstName": "Vahn", "lastName": "Lackey", "batterStats": {"atBats": "4"}},
    ]}
    roster = pbp.roster_from_boxscore(team_box)
    assert roster[0]["key"] == roster[1]["key"], "same player must get one identity"
    assert roster[0]["lastName"] == "Lackey" and roster[0]["firstName"] == "Vahn"


def test_packed_name_roster_still_matches_pbp_surname():
    team_box = {"playerStats": [
        {"firstName": "", "lastName": "Kent Schmidt", "batterStats": {"atBats": "3"}}]}
    roster = pbp.roster_from_boxscore(team_box)
    assert pbp.match_player("Kent Schmidt", roster) == roster[0]["key"]
    assert pbp.match_player("Schmidt, K.", roster) == roster[0]["key"]


def test_suffix_name_packed_into_lastname():
    team_box = {"playerStats": [
        {"firstName": "", "lastName": "Bubba Chandler Jr.", "batterStats": {"atBats": "1"}}]}
    roster = pbp.roster_from_boxscore(team_box)
    assert roster[0]["lastName"] == "Chandler"
