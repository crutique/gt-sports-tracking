import pytest

from pipeline import college_metrics as cm


def _b(**kw):
    base = dict(ab=0, r=0, h=0, d=0, t=0, hr=0, rbi=0, bb=0, k=0, hbp=0, sb=0, cs=0, sf=0, sh=0)
    base.update(kw)
    return base


def _p(**kw):
    base = dict(g=0, gs=0, ip_outs=0, w=0, l=0, sv=0, h=0, r=0, er=0, bb=0, k=0, hb=0, hr=0)
    base.update(kw)
    return base


def test_singles_and_iso():
    b = _b(ab=40, h=16, d=4, t=1, hr=2)  # 1B = 16-4-1-2 = 9
    assert cm.singles(b) == 9
    # SLG = (16 + 4 + 2*1 + 3*2)/40 = 28/40 = .700 ; AVG = .400 ; ISO = .300
    assert cm.iso(b) == pytest.approx(0.300, abs=1e-3)


def test_woba_matches_hand_calc():
    b = _b(ab=10, h=4, d=1, hr=1, bb=2, hbp=1, sf=0)  # 1B = 4-1-0-1 = 2
    w = cm.WOBA_WEIGHTS
    denom = 10 + 2 + 0 + 1  # AB+BB+SF+HBP
    num = w["bb"] * 2 + w["hbp"] * 1 + w["1b"] * 2 + w["2b"] * 1 + w["hr"] * 1
    assert cm.woba(b) == pytest.approx(num / denom, abs=1e-9)


def test_woba_needs_denominator():
    assert cm.woba(_b()) is None


def test_league_average_hitter_scores_100_wrc():
    pool = [
        _b(ab=100, r=15, h=30, d=6, t=1, hr=4, bb=12, k=20, hbp=2, sf=1),
        _b(ab=90, r=10, h=22, d=4, t=0, hr=2, bb=8, k=25, hbp=1, sf=1),
    ]
    pit = [_p(ip_outs=90, er=10, h=25, bb=8, k=30, hb=1, hr=2)]
    c = cm.league_constants(pool, pit)
    # a hitter whose wOBA is exactly league-average must land at wRC+ = 100
    assert cm.wrc_plus(c["lgwOBA"], c) == 100
    assert c["lgwOBA"] > 0 and c["wobaScale"] > 0 and c["lgRPA"] > 0


def test_league_average_pitcher_fip_equals_league_era():
    pit = [
        _p(ip_outs=90, er=10, h=25, bb=8, k=30, hb=1, hr=2),
        _p(ip_outs=60, er=9, h=20, bb=6, k=18, hb=0, hr=3),
    ]
    c = cm.league_constants([_b(ab=50, h=15, bb=5, r=8)], pit)
    # the aggregate pitcher (pool totals) has FIP == league ERA by construction
    agg = _p(ip_outs=150, er=19, h=45, bb=14, k=48, hb=1, hr=5)
    assert cm.fip(agg, c["fipConstant"]) == pytest.approx(c["lgERA"], abs=0.02)


def test_era_plus():
    assert cm.era_plus(3.0, 4.5) == 150   # 100 * 4.5 / 3.0
    assert cm.era_plus(4.5, 4.5) == 100
    assert cm.era_plus(None, 4.5) is None
