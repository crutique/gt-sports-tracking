import pytest

from pipeline import college
from pipeline import college_metrics as cm

# A small but realistic D1 pool: three hitters on three teams, two pitchers.
BATTING = [
    {"stats_id": "a", "name": "A", "team": "T1", "g": 50, "ab": 190, "r": 45, "h": 66,
     "d": 14, "t": 1, "hr": 14, "rbi": 55, "bb": 30, "k": 32, "hbp": 6, "sf": 3, "sh": 0, "sb": 8, "cs": 2},
    {"stats_id": "b", "name": "B", "team": "T2", "g": 50, "ab": 200, "r": 30, "h": 54,
     "d": 10, "t": 1, "hr": 6, "rbi": 32, "bb": 18, "k": 45, "hbp": 3, "sf": 2, "sh": 1, "sb": 4, "cs": 1},
    {"stats_id": "c", "name": "C", "team": "T3", "g": 48, "ab": 175, "r": 20, "h": 40,
     "d": 7, "t": 0, "hr": 2, "rbi": 18, "bb": 12, "k": 50, "hbp": 2, "sf": 1, "sh": 2, "sb": 1, "cs": 0},
]
PITCHING = [
    {"stats_id": "p1", "name": "P1", "team": "T1", "g": 16, "gs": 15, "ip_outs": 300, "w": 8, "l": 2,
     "sv": 0, "h": 80, "r": 35, "er": 30, "bb": 25, "k": 120, "hb": 6, "hr": 7},
    {"stats_id": "p2", "name": "P2", "team": "T2", "g": 18, "gs": 14, "ip_outs": 255, "w": 5, "l": 5,
     "sv": 1, "h": 95, "r": 60, "er": 55, "bb": 45, "k": 62, "hb": 9, "hr": 14},
]
STATS = {"batting": BATTING, "pitching": PITCHING}


def test_block_shapes_counting_rates_advanced():
    b = college.college_bundle(STATS, wanted={"a", "p1"}, tier=1)
    a = b["a"]["hitting"]
    assert a["counting"]["hr"] == 14
    assert a["rates"]["avg"] == pytest.approx(66 / 190, abs=1e-3)
    # advanced layer present and sane
    assert a["advanced"]["iso"] == pytest.approx(a["rates"]["slg"] - a["rates"]["avg"], abs=1e-3)
    assert isinstance(a["advanced"]["wrcPlus"], int)
    assert a["advanced"]["woba"] > 0
    p = b["p1"]["pitching"]
    assert p["counting"]["ip"] == "100.0"
    assert p["advanced"]["fip"] is not None
    assert isinstance(p["advanced"]["eraPlus"], int)
    assert b["a"]["pitching"] is None


def test_d1_panel_has_standard_and_advanced_sliders():
    b = college.college_bundle(STATS, wanted={"a"}, tier=1)
    metrics = {s["metric"] for s in b["a"]["hitting"]["sliders"]}
    assert {"ops", "avg", "obp", "slg", "kPct", "bbPct"} <= metrics   # standard
    assert {"wrcPlus", "woba", "iso"} <= metrics                       # advanced
    # A is the run-away best hitter -> unique best OPS of the qualified pool -> 100
    ops = {s["metric"]: s for s in b["a"]["hitting"]["sliders"]}["ops"]
    assert ops["percentile"] == 100


def test_wrc_plus_is_league_relative_to_100():
    # league-average wRC+ (from consts) must be 100 by construction
    consts = cm.league_constants(BATTING, PITCHING)
    assert cm.wrc_plus(consts["lgwOBA"], consts) == 100
    b = college.college_bundle(STATS, wanted={"a"}, tier=1)
    # the league-avg marker on the wRC+ slider sits at 100
    wrc = {s["metric"]: s for s in b["a"]["hitting"]["sliders"]}["wrcPlus"]
    assert wrc["leagueAvg"] == 100


def test_fip_slider_is_inverted_lower_is_better():
    b = college.college_bundle(STATS, wanted={"p1", "p2"}, tier=1)
    p1 = {s["metric"]: s for s in b["p1"]["pitching"]["sliders"]}
    p2 = {s["metric"]: s for s in b["p2"]["pitching"]["sliders"]}
    # P1 has by far the better (lower) FIP -> higher percentile despite inversion
    assert b["p1"]["pitching"]["advanced"]["fip"] < b["p2"]["pitching"]["advanced"]["fip"]
    assert p1["fip"]["percentile"] > p2["fip"]["percentile"]


def test_non_d1_gets_no_percentile_panel_but_keeps_advanced():
    b = college.college_bundle(STATS, wanted={"a", "p1"}, tier=2)
    assert b["a"]["hitting"]["sliders"] is None
    assert b["p1"]["pitching"]["sliders"] is None
    # rates + advanced still computed (the toggle + numbers still work off-D1)
    assert b["a"]["hitting"]["rates"]["ops"] is not None
    assert b["a"]["hitting"]["advanced"]["wrcPlus"] is not None
    assert b["p1"]["pitching"]["advanced"]["fip"] is not None


def test_absent_wanted_player_omitted():
    b = college.college_bundle(STATS, wanted={"ghost"}, tier=1)
    assert "ghost" not in b
