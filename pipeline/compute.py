"""Turn one league's canonical tables + game logs into per-player stat blocks."""
from pipeline import percentiles as pc
from pipeline import stats_math as sm

_BAT_AGG = ("ab", "h", "d", "t", "hr", "bb", "hbp", "sf", "sh", "k")
_PIT_AGG = ("ip_outs", "h", "er", "bb", "k", "hb", "hr")
# metrics whose value depends on a derived denominator (PA / BF / AB-faced)
_DERIVED = {"hitting": {"kPct", "bbPct"}, "pitching": {"kPct", "bbPct", "oppAvg"}}

# Qualifying bars, scaled to each team's games played so they track season
# length. Summer play is sporadic, so these sit below MLB's rate-title bars
# (3.1 PA / 1.0 IP per team game): a hitter needs 2.0 PA per team game, a
# pitcher 0.5 IP per team game. Non-qualifiers still get a percentile (vs. the
# qualified pool) but the site renders it hatched.
HIT_PA_PER_G = 2.0
PIT_IP_PER_G = 0.5


def _aggregate(rows, keys):
    return {k: sum(r.get(k, 0) or 0 for r in rows) for k in keys}


def _sliders(side, metrics, my_rates, qual_rates, lg_avgs, tier, qualified, native_denoms=False):
    if tier != 1:
        return None
    out = []
    for m in metrics:
        value = my_rates.get(m)
        if value is None:
            continue
        pool = [r[m] for r in qual_rates if r.get(m) is not None]
        if not pool:
            continue
        # NOTE: a tied leader can legitimately show <100 (midrank splits ties);
        # correct math, not a display bug.
        lg_avg = lg_avgs.get(m)
        out.append({
            "metric": m, "value": round(value, 4),
            "percentile": pc.midrank_percentile(pool, value, invert=pc.is_inverted(side, m), in_pool=qualified),
            "leagueAvg": round(lg_avg, 4) if lg_avg is not None else None,
            "leagueAvgPercentile": (pc.midrank_percentile(pool, lg_avg, invert=pc.is_inverted(side, m))
                                    if lg_avg is not None else None),
            "derived": m in _DERIVED[side] and not (native_denoms and m != "oppAvg"),
        })
    return out


def _hitting_block(row, qual_rates, lg_avgs, tier, qualified):
    counting = {k: row.get(k, 0) or 0 for k in
                ("g", "ab", "r", "h", "d", "t", "hr", "rbi", "bb", "k", "hbp", "sb", "cs")}
    rates = sm.batting_rates(row)
    return {"counting": counting, "rates": rates, "qualified": qualified,
            "sliders": _sliders("hitting", pc.HITTER_SLIDERS, rates, qual_rates, lg_avgs, tier, qualified,
                               native_denoms=bool(row.get("pa")))}


def _pitching_block(row, qual_rates, lg_avgs, tier, qualified):
    counting = {k: row.get(k, 0) or 0 for k in
                ("g", "gs", "w", "l", "sv", "hld", "h", "r", "er", "bb", "k", "hb", "hr")}
    counting["ip"] = sm.outs_to_ip_str(row.get("ip_outs", 0) or 0)
    rates = sm.pitching_rates(row)
    return {"counting": counting, "rates": rates, "qualified": qualified,
            "sliders": _sliders("pitching", pc.PITCHER_SLIDERS, rates, qual_rates, lg_avgs, tier, qualified,
                               native_denoms=bool(row.get("bf")))}


def _team_games(rows):
    """Games the furthest-along player on each team has played ~= team schedule."""
    tg = {}
    for r in rows.values():
        t = r.get("team", "")
        tg[t] = max(tg.get(t, 0), r.get("g", 0) or 0)
    return tg


def league_bundle(cfg, stats, logs, wanted):
    tier = cfg.get("tier")
    bat_rows = {r["stats_id"]: r for r in stats.get("batting", [])}
    pit_rows = {r["stats_id"]: r for r in stats.get("pitching", [])}
    bat_tg, pit_tg = _team_games(bat_rows), _team_games(pit_rows)

    def bat_qual(r):
        tg = bat_tg.get(r.get("team", ""), 0)
        return tg > 0 and sm.pa(r) >= HIT_PA_PER_G * tg

    def pit_qual(r):
        tg = pit_tg.get(r.get("team", ""), 0)
        return tg > 0 and (r.get("ip_outs", 0) or 0) >= PIT_IP_PER_G * 3 * tg

    # rank against qualified players; if none qualify yet (early season), fall
    # back to the whole pool so percentiles still render (all read non-qualified)
    bat_qual_rates = [sm.batting_rates(r) for r in bat_rows.values() if sm.pa(r) > 0 and bat_qual(r)]
    pit_qual_rates = [sm.pitching_rates(r) for r in pit_rows.values() if sm.bf(r) > 0 and pit_qual(r)]
    if not bat_qual_rates:
        bat_qual_rates = [sm.batting_rates(r) for r in bat_rows.values() if sm.pa(r) > 0]
    if not pit_qual_rates:
        pit_qual_rates = [sm.pitching_rates(r) for r in pit_rows.values() if sm.bf(r) > 0]

    lg_bat = sm.batting_rates(_aggregate(list(bat_rows.values()), _BAT_AGG))
    lg_pit = sm.pitching_rates(_aggregate(list(pit_rows.values()), _PIT_AGG))

    bundle = {}
    for sid in wanted:
        hit = (_hitting_block(bat_rows[sid], bat_qual_rates, lg_bat, tier, bat_qual(bat_rows[sid]))
               if sid in bat_rows else None)
        pit = (_pitching_block(pit_rows[sid], pit_qual_rates, lg_pit, tier, pit_qual(pit_rows[sid]))
               if sid in pit_rows else None)
        if hit is None and pit is None:
            continue  # absent from both tables -> omit so output.assemble carries forward prior data
        bundle[sid] = {"hitting": hit, "pitching": pit, "gamelog": logs.get(sid, [])}
    return bundle
