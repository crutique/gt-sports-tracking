"""Turn one league's canonical tables + game logs into per-player stat blocks."""
from pipeline import percentiles as pc
from pipeline import stats_math as sm

_BAT_AGG = ("ab", "h", "d", "t", "hr", "bb", "hbp", "sf", "sh", "k")
_PIT_AGG = ("ip_outs", "h", "er", "bb", "k", "hb", "hr")
# metrics whose value depends on a derived denominator (PA / BF / AB-faced)
_DERIVED = {"hitting": {"kPct", "bbPct"}, "pitching": {"kPct", "bbPct", "oppAvg"}}


def _aggregate(rows, keys):
    return {k: sum(r.get(k, 0) or 0 for r in rows) for k in keys}


def _sliders(side, metrics, my_rates, all_rates, lg_avgs, tier):
    if tier != 1:
        return None
    out = []
    for m in metrics:
        value = my_rates.get(m)
        if value is None:
            continue
        pool = [r[m] for r in all_rates if r.get(m) is not None]
        # NOTE: a tied league leader can legitimately show <99 (midrank splits ties);
        # correct math, not a display bug.
        lg_avg = lg_avgs.get(m)
        out.append({
            "metric": m, "value": round(value, 4),
            "percentile": pc.midrank_percentile(pool, value, invert=pc.is_inverted(side, m)),
            "leagueAvg": round(lg_avg, 4) if lg_avg is not None else None,
            "leagueAvgPercentile": (pc.midrank_percentile(pool, lg_avg,
                                                          invert=pc.is_inverted(side, m))
                                    if lg_avg is not None else None),
            "derived": m in _DERIVED[side],
        })
    return out


def _hitting_block(row, all_rates, lg_avgs, tier):
    counting = {k: row.get(k, 0) or 0 for k in
                ("g", "ab", "r", "h", "d", "t", "hr", "rbi", "bb", "k", "hbp", "sb", "cs")}
    rates = sm.batting_rates(row)
    return {"counting": counting, "rates": rates,
            "sliders": _sliders("hitting", pc.HITTER_SLIDERS, rates, all_rates, lg_avgs, tier)}


def _pitching_block(row, all_rates, lg_avgs, tier):
    counting = {k: row.get(k, 0) or 0 for k in
                ("g", "gs", "w", "l", "sv", "hld", "h", "r", "er", "bb", "k", "hb", "hr")}
    counting["ip"] = sm.outs_to_ip_str(row.get("ip_outs", 0) or 0)
    rates = sm.pitching_rates(row)
    return {"counting": counting, "rates": rates,
            "sliders": _sliders("pitching", pc.PITCHER_SLIDERS, rates, all_rates, lg_avgs, tier)}


def league_bundle(cfg, stats, logs, wanted):
    tier = cfg.get("tier")
    bat_rows = {r["stats_id"]: r for r in stats.get("batting", [])}
    pit_rows = {r["stats_id"]: r for r in stats.get("pitching", [])}
    bat_rates = [sm.batting_rates(r) for r in bat_rows.values() if sm.pa(r) > 0]
    pit_rates = [sm.pitching_rates(r) for r in pit_rows.values() if sm.bf(r) > 0]  # nonzero IP or BF per spec
    lg_bat = sm.batting_rates(_aggregate(list(bat_rows.values()), _BAT_AGG))
    lg_pit = sm.pitching_rates(_aggregate(list(pit_rows.values()), _PIT_AGG))

    bundle = {}
    for sid in wanted:
        hit = _hitting_block(bat_rows[sid], bat_rates, lg_bat, tier) if sid in bat_rows else None
        pit = _pitching_block(pit_rows[sid], pit_rates, lg_pit, tier) if sid in pit_rows else None
        if hit is None and pit is None:
            continue  # absent from both tables -> omit so output.assemble carries forward prior data
        bundle[sid] = {"hitting": hit, "pitching": pit, "gamelog": logs.get(sid, [])}
    return bundle
