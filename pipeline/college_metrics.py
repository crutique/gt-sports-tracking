"""Advanced college batting/pitching metrics — wOBA, wRC+, FIP, ERA+, ISO — on
the canonical counting rows used elsewhere in the pipeline (same keys as
``pipeline.stats_math``: ab, h, d, t, hr, bb, hbp, sf, sh, k, r for hitters;
ip_outs, er, h, bb, k, hb, hr for pitchers).

Design (per docs/data-sources.md research):
- **Raw counting inputs must be exact** — HBP and SF included, no gap-filling.
  wOBA/PA are wrong without them, so callers must supply complete lines.
- **Linear weights are a documented, swappable default** — the MLB-like weight
  family FanGraphs/College Splits use for college. When a run-expectancy matrix
  (from play-by-play) exists, swap WOBA_WEIGHTS for the college-derived set.
- **League-relative constants are derived from the ACTUAL D1 pool** passed in
  (lgwOBA, wOBA scale, lgR/PA, lgERA, FIP constant) — never a hardcoded fudge.
  So wRC+/FIP/ERA+ are internally consistent with the season they rank within.

Percentiles reuse ``pipeline.percentiles``; rates reuse ``pipeline.stats_math``.
"""
from pipeline.stats_math import batting_rates, pa

# Relative run values per offensive event. Swap for PBP-run-expectancy-derived
# college weights once that pipeline exists — the constants below rescale to the
# pool regardless, so wRC+ stays league-relative either way.
WOBA_WEIGHTS = {"bb": 0.69, "hbp": 0.72, "1b": 0.89, "2b": 1.27, "3b": 1.62, "hr": 2.10}


def _g(row, key):
    return row.get(key, 0) or 0


def singles(b):
    """1B = H - 2B - 3B - HR."""
    return _g(b, "h") - _g(b, "d") - _g(b, "t") - _g(b, "hr")


def iso(b):
    """Isolated power = SLG - AVG."""
    r = batting_rates(b)
    if r["slg"] is None or r["avg"] is None:
        return None
    return round(r["slg"] - r["avg"], 3)


def woba(b, weights=WOBA_WEIGHTS):
    """Unscaled wOBA. Denominator AB+BB+SF+HBP (IBB not tracked at NCAA level)."""
    denom = _g(b, "ab") + _g(b, "bb") + _g(b, "sf") + _g(b, "hbp")
    if not denom:
        return None
    num = (weights["bb"] * _g(b, "bb") + weights["hbp"] * _g(b, "hbp")
           + weights["1b"] * singles(b) + weights["2b"] * _g(b, "d")
           + weights["3b"] * _g(b, "t") + weights["hr"] * _g(b, "hr"))
    return num / denom


def league_constants(batting_pool, pitching_pool, weights=WOBA_WEIGHTS):
    """Derive league-relative constants from the full D1 pool for a season.

    Returns weights, lgwOBA, wobaScale (=lgOBP/lgwOBA), lgRPA, lgERA, fipConstant.
    """
    def tot(pool, k):
        return sum(_g(r, k) for r in pool)

    lg_denom = (tot(batting_pool, "ab") + tot(batting_pool, "bb")
                + tot(batting_pool, "sf") + tot(batting_pool, "hbp"))
    lg_singles = sum(singles(b) for b in batting_pool)
    lg_woba_num = (weights["bb"] * tot(batting_pool, "bb") + weights["hbp"] * tot(batting_pool, "hbp")
                   + weights["1b"] * lg_singles + weights["2b"] * tot(batting_pool, "d")
                   + weights["3b"] * tot(batting_pool, "t") + weights["hr"] * tot(batting_pool, "hr"))
    lg_woba = lg_woba_num / lg_denom if lg_denom else None
    lg_obp = ((tot(batting_pool, "h") + tot(batting_pool, "bb") + tot(batting_pool, "hbp")) / lg_denom
              if lg_denom else None)
    woba_scale = lg_obp / lg_woba if lg_woba else None
    lg_pa = sum(pa(b) for b in batting_pool)
    lg_rpa = tot(batting_pool, "r") / lg_pa if lg_pa else None

    lg_ip = tot(pitching_pool, "ip_outs") / 3
    lg_era = 9 * tot(pitching_pool, "er") / lg_ip if lg_ip else None
    fip_kernel = ((13 * tot(pitching_pool, "hr") + 3 * (tot(pitching_pool, "bb") + tot(pitching_pool, "hb"))
                   - 2 * tot(pitching_pool, "k")) / lg_ip) if lg_ip else None
    fip_constant = (lg_era - fip_kernel) if (lg_era is not None and fip_kernel is not None) else None

    return {
        "weights": weights, "lgwOBA": lg_woba, "wobaScale": woba_scale,
        "lgRPA": lg_rpa, "lgERA": lg_era, "fipConstant": fip_constant,
    }


def wrc_plus(woba_val, consts):
    """Simplified wRC+ (no park factor): league-average hitter = 100."""
    if woba_val is None or not consts.get("lgwOBA") or not consts.get("wobaScale") or not consts.get("lgRPA"):
        return None
    wraa_per_pa = (woba_val - consts["lgwOBA"]) / consts["wobaScale"]
    return round((wraa_per_pa + consts["lgRPA"]) / consts["lgRPA"] * 100)


def fip(p, fip_constant):
    """FIP = (13*HR + 3*(BB+HBP) - 2*K)/IP + cFIP. Scaled to league ERA."""
    ip = _g(p, "ip_outs") / 3
    if not ip or fip_constant is None:
        return None
    return round((13 * _g(p, "hr") + 3 * (_g(p, "bb") + _g(p, "hb")) - 2 * _g(p, "k")) / ip + fip_constant, 2)


def era_plus(era_val, lg_era):
    """ERA+ (no park factor): league-average pitcher = 100, higher is better."""
    if not era_val or lg_era is None:
        return None
    return round(100 * lg_era / era_val)
