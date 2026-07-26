"""D1 college per-season stat blocks: counting + rates + advanced + (D1-only)
percentiles, from canonical counting rows.

Parallels :mod:`pipeline.compute` (summer leagues) but adds the sabermetric layer
(:mod:`pipeline.college_metrics`: wOBA / wRC+ / FIP / ERA+ / ISO) and gates the
Baseball-Savant-style percentile panel to Division-I seasons (``tier == 1``) —
no D2 / D3 / NJCAA / HS panels, per product direction. Rates and advanced metrics
still compute for every division; only the percentile panel is D1-only.

Canonical keys match :mod:`pipeline.stats_math`:
  hitters:  ab h d t hr bb hbp sf sh k r rbi sb cs g (pa)
  pitchers: ip_outs er h bb k hb hr g gs w l sv (bf)

The league-relative constants (lgwOBA, wOBA scale, lgERA, FIP constant) are
derived from the *actual* pool passed in — so wRC+/FIP/ERA+ are internally
consistent with the season they rank within, never a hardcoded fudge.
"""
from pipeline import college_metrics as cm
from pipeline import percentiles as pc
from pipeline import stats_math as sm

_BAT_AGG = ("ab", "h", "d", "t", "hr", "bb", "hbp", "sf", "sh", "k", "r")
_PIT_AGG = ("ip_outs", "h", "er", "bb", "k", "hb", "hr")

# NCAA rate-qualifier bars, scaled to each team's games played (batting: 2.0 PA
# per team game; pitching: 0.8 IP per team game — the historical NCAA cutoffs).
# Non-qualifiers still receive a percentile vs. the qualified pool; the site
# renders it hatched, exactly as in the summer engine.
HIT_PA_PER_G = 2.0
PIT_IP_PER_G = 0.8

# Advanced metrics that also earn a percentile in the D1 panel. Orientation:
# wRC+, wOBA, ISO, ERA+ are higher-is-better; FIP is lower-is-better.
HIT_ADV = ("wrcPlus", "woba", "iso")
PIT_ADV = ("fip", "eraPlus")
_ADV_INVERT = {"fip"}


def _agg(rows, keys):
    return {k: sum(r.get(k, 0) or 0 for r in rows) for k in keys}


def _team_games(rows):
    """Games the furthest-along player on each team has played ~= team schedule."""
    tg = {}
    for r in rows.values():
        t = r.get("team", "")
        tg[t] = max(tg.get(t, 0), r.get("g", 0) or 0)
    return tg


def hit_advanced(row, consts):
    """wRC+, wOBA (scaled, displayable), ISO for one hitter row."""
    w = cm.woba(row)
    return {
        "wrcPlus": cm.wrc_plus(w, consts),
        "woba": round(w, 3) if w is not None else None,
        "iso": cm.iso(row),
    }


def pit_advanced(row, consts):
    """FIP, ERA+ for one pitcher row."""
    era = sm.pitching_rates(row)["era"]
    return {
        "fip": cm.fip(row, consts.get("fipConstant")),
        "eraPlus": cm.era_plus(era, consts.get("lgERA")),
    }


def _slider(metric, value, pool_values, invert, lg_avg, qualified):
    """One percentile row, shaped exactly like compute._sliders' output so the
    site renders college and summer panels with the same component."""
    if value is None:
        return None
    pool = [v for v in pool_values if v is not None]
    if not pool:
        return None
    return {
        "metric": metric,
        "value": round(value, 4),
        "percentile": pc.midrank_percentile(pool, value, invert=invert, in_pool=qualified),
        "leagueAvg": round(lg_avg, 4) if lg_avg is not None else None,
        "leagueAvgPercentile": (pc.midrank_percentile(pool, lg_avg, invert=invert)
                                if lg_avg is not None else None),
    }


def _hit_panel(rate_pool, adv_pool, lg_rates, lg_adv, my_rates, my_adv, qualified):
    out = []
    for m in pc.HITTER_SLIDERS:
        s = _slider(m, my_rates.get(m), [r.get(m) for r in rate_pool],
                    pc.is_inverted("hitting", m), lg_rates.get(m), qualified)
        if s:
            out.append(s)
    for m in HIT_ADV:
        s = _slider(m, my_adv.get(m), [a.get(m) for a in adv_pool],
                    m in _ADV_INVERT, lg_adv.get(m), qualified)
        if s:
            out.append(s)
    return out


def _pit_panel(rate_pool, adv_pool, lg_rates, lg_adv, my_rates, my_adv, qualified):
    out = []
    for m in pc.PITCHER_SLIDERS:
        s = _slider(m, my_rates.get(m), [r.get(m) for r in rate_pool],
                    pc.is_inverted("pitching", m), lg_rates.get(m), qualified)
        if s:
            out.append(s)
    for m in PIT_ADV:
        s = _slider(m, my_adv.get(m), [a.get(m) for a in adv_pool],
                    m in _ADV_INVERT, lg_adv.get(m), qualified)
        if s:
            out.append(s)
    return out


def _hitting_block(row, consts, rate_pool, adv_pool, lg_rates, lg_adv, tier, qualified):
    counting = {k: row.get(k, 0) or 0 for k in
                ("g", "ab", "r", "h", "d", "t", "hr", "rbi", "bb", "k", "hbp", "sf", "sb", "cs")}
    rates = sm.batting_rates(row)
    adv = hit_advanced(row, consts)
    panel = (_hit_panel(rate_pool, adv_pool, lg_rates, lg_adv, rates, adv, qualified)
             if tier == 1 else None)
    return {"counting": counting, "rates": rates, "advanced": adv,
            "qualified": qualified, "sliders": panel}


def _pitching_block(row, consts, rate_pool, adv_pool, lg_rates, lg_adv, tier, qualified):
    counting = {k: row.get(k, 0) or 0 for k in
                ("g", "gs", "w", "l", "sv", "h", "r", "er", "bb", "k", "hb", "hr")}
    counting["ip"] = sm.outs_to_ip_str(row.get("ip_outs", 0) or 0)
    rates = sm.pitching_rates(row)
    adv = pit_advanced(row, consts)
    panel = (_pit_panel(rate_pool, adv_pool, lg_rates, lg_adv, rates, adv, qualified)
             if tier == 1 else None)
    return {"counting": counting, "rates": rates, "advanced": adv,
            "qualified": qualified, "sliders": panel}


def college_bundle(stats, wanted, tier):
    """Pool -> per-player {hitting, pitching} blocks for the ``wanted`` ids.

    ``stats`` is ``{"batting": [rows], "pitching": [rows]}`` of the *entire* pool
    for one season+division (every row carries ``stats_id`` and ``team``).
    ``tier`` is the NCAA division (1/2/3); percentiles only populate for tier 1.
    """
    bat_rows = {r["stats_id"]: r for r in stats.get("batting", [])}
    pit_rows = {r["stats_id"]: r for r in stats.get("pitching", [])}
    consts = cm.league_constants(list(bat_rows.values()), list(pit_rows.values()))
    bat_tg, pit_tg = _team_games(bat_rows), _team_games(pit_rows)

    def bat_qual(r):
        tg = bat_tg.get(r.get("team", ""), 0)
        return tg > 0 and sm.pa(r) >= HIT_PA_PER_G * tg

    def pit_qual(r):
        tg = pit_tg.get(r.get("team", ""), 0)
        return tg > 0 and (r.get("ip_outs", 0) or 0) >= PIT_IP_PER_G * 3 * tg

    # Qualified pools for percentile ranking; fall back to the whole pool if none
    # qualify (all then read non-qualified), mirroring the summer engine.
    bat_qual_rows = [r for r in bat_rows.values() if sm.pa(r) > 0 and bat_qual(r)]
    pit_qual_rows = [r for r in pit_rows.values() if sm.bf(r) > 0 and pit_qual(r)]
    if not bat_qual_rows:
        bat_qual_rows = [r for r in bat_rows.values() if sm.pa(r) > 0]
    if not pit_qual_rows:
        pit_qual_rows = [r for r in pit_rows.values() if sm.bf(r) > 0]

    bat_rate_pool = [sm.batting_rates(r) for r in bat_qual_rows]
    pit_rate_pool = [sm.pitching_rates(r) for r in pit_qual_rows]
    bat_adv_pool = [hit_advanced(r, consts) for r in bat_qual_rows]
    pit_adv_pool = [pit_advanced(r, consts) for r in pit_qual_rows]

    lg_bat = sm.batting_rates(_agg(list(bat_rows.values()), _BAT_AGG))
    lg_pit = sm.pitching_rates(_agg(list(pit_rows.values()), _PIT_AGG))
    lg_hit_adv = {"wrcPlus": 100, "woba": round(consts["lgwOBA"], 3) if consts["lgwOBA"] else None,
                  "iso": cm.iso(_agg(list(bat_rows.values()), _BAT_AGG))}
    lg_pit_adv = {"fip": round(consts["lgERA"], 2) if consts["lgERA"] is not None else None,
                  "eraPlus": 100}

    bundle = {}
    for sid in wanted:
        hit = (_hitting_block(bat_rows[sid], consts, bat_rate_pool, bat_adv_pool, lg_bat, lg_hit_adv,
                              tier, bat_qual(bat_rows[sid])) if sid in bat_rows else None)
        pit = (_pitching_block(pit_rows[sid], consts, pit_rate_pool, pit_adv_pool, lg_pit, lg_pit_adv,
                               tier, pit_qual(pit_rows[sid])) if sid in pit_rows else None)
        if hit is None and pit is None:
            continue
        bundle[sid] = {"hitting": hit, "pitching": pit}
    return bundle
