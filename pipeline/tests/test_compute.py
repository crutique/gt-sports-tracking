import pytest
from pipeline import compute

BATTING = [
    {"stats_id": "a", "name": "A", "team": "T1", "g": 10, "ab": 40, "r": 8, "h": 16,
     "d": 4, "t": 0, "hr": 2, "rbi": 10, "bb": 6, "k": 8, "hbp": 1, "sb": 3, "cs": 1, "sf": 1, "sh": 0},
    {"stats_id": "b", "name": "B", "team": "T2", "g": 10, "ab": 42, "r": 4, "h": 10,
     "d": 2, "t": 0, "hr": 0, "rbi": 4, "bb": 3, "k": 12, "hbp": 0, "sb": 1, "cs": 0, "sf": 0, "sh": 1},
    {"stats_id": "c", "name": "C", "team": "T3", "g": 9, "ab": 30, "r": 3, "h": 6,
     "d": 1, "t": 0, "hr": 1, "rbi": 3, "bb": 2, "k": 11, "hbp": 0, "sb": 0, "cs": 0, "sf": 0, "sh": 0},
]
PITCHING = [
    {"stats_id": "p1", "name": "P1", "team": "T1", "g": 5, "gs": 5, "ip_outs": 90, "w": 3, "l": 0,
     "sv": 0, "hld": 0, "h": 20, "r": 8, "er": 7, "bb": 8, "k": 33, "hb": 1, "hr": 1},
    {"stats_id": "p2", "name": "P2", "team": "T2", "g": 6, "gs": 0, "ip_outs": 45, "w": 1, "l": 1,
     "sv": 2, "hld": 1, "h": 18, "r": 11, "er": 10, "bb": 9, "k": 12, "hb": 0, "hr": 2},
]
LOGS = {"a": [{"date": "2026-07-12", "opponent": "at T2", "ab": 4, "r": 1, "h": 2,
               "d": 0, "t": 0, "hr": 1, "rbi": 3, "bb": 0, "k": 1, "sb": 0}]}
CFG = {"tier": 1}


def test_bundle_shapes_and_percentiles():
    bundle = compute.league_bundle(CFG, {"batting": BATTING, "pitching": PITCHING}, LOGS,
                                   wanted={"a", "p1"})
    a = bundle["a"]["hitting"]
    assert a["counting"]["hr"] == 2
    assert a["rates"]["avg"] == pytest.approx(0.400, abs=1e-3)
    sliders = {s["metric"]: s for s in a["sliders"]}
    assert set(sliders) == {"ops", "avg", "obp", "slg", "kPct", "bbPct"}
    # A has the best OPS of 3 -> midrank 2.5/3 -> 83
    assert sliders["ops"]["percentile"] == 83
    # league avg OPS computed from AGGREGATE totals, not mean of rates
    agg = {k: sum(r[k] for r in BATTING) for k in
           ("ab", "h", "d", "t", "hr", "bb", "hbp", "sf", "sh", "k")}
    from pipeline import stats_math as sm
    # leagueAvg is stored rounded to 4 decimals, so compare loosely
    assert sliders["ops"]["leagueAvg"] == pytest.approx(sm.batting_rates(agg)["ops"], abs=1e-4)
    assert bundle["a"]["gamelog"] == LOGS["a"]
    assert bundle["a"]["pitching"] is None
    p1 = bundle["p1"]["pitching"]
    assert p1["counting"]["ip"] == "30.0"
    psliders = {s["metric"]: s for s in p1["sliders"]}
    # P1 has the better ERA of 2 -> inverted -> high percentile
    assert psliders["era"]["percentile"] > 50
    assert bundle["p1"]["gamelog"] == []


def test_tier2_league_gets_no_sliders():
    bundle = compute.league_bundle({"tier": 2}, {"batting": BATTING, "pitching": PITCHING},
                                   {}, wanted={"a"})
    assert bundle["a"]["hitting"]["sliders"] is None
    assert bundle["a"]["hitting"]["rates"]["avg"] is not None


def test_derived_flag_set_when_pa_not_native():
    bundle = compute.league_bundle(CFG, {"batting": BATTING, "pitching": PITCHING},
                                   {}, wanted={"a"})
    sliders = {s["metric"]: s for s in bundle["a"]["hitting"]["sliders"]}
    assert sliders["kPct"]["derived"] is True   # PA derived from counting stats
    assert sliders["ops"]["derived"] is False


def test_absent_wanted_player_omitted_for_carry_forward():
    bundle = compute.league_bundle(CFG, {"batting": BATTING, "pitching": PITCHING},
                                   {}, wanted={"ghost"})
    assert "ghost" not in bundle


def test_zero_out_pitcher_counts_toward_bf_pools():
    pitching = PITCHING + [{"stats_id": "p3", "name": "P3", "team": "T3", "g": 1, "gs": 0,
                            "ip_outs": 0, "w": 0, "l": 0, "sv": 0, "hld": 0,
                            "h": 2, "r": 3, "er": 3, "bb": 1, "k": 0, "hb": 0, "hr": 1}]
    bundle = compute.league_bundle(CFG, {"batting": BATTING, "pitching": pitching},
                                   {}, wanted={"p3"})
    sliders = {s["metric"]: s for s in bundle["p3"]["pitching"]["sliders"]}
    # ip-denominated metrics skipped (rate is None); BF-denominated ones computed, no crash
    assert "era" not in sliders and "kPct" in sliders and "oppAvg" in sliders
    assert bundle["p3"]["pitching"]["rates"]["era"] is None


def test_slider_includes_league_avg_percentile():
    bundle = compute.league_bundle(CFG, {"batting": BATTING, "pitching": PITCHING},
                                   {}, wanted={"a"})
    sliders = {s["metric"]: s for s in bundle["a"]["hitting"]["sliders"]}
    ops = sliders["ops"]
    assert isinstance(ops["leagueAvgPercentile"], int)
    assert 0 <= ops["leagueAvgPercentile"] <= 99
    # league avg is below the best hitter's percentile
    assert ops["leagueAvgPercentile"] < ops["percentile"]
