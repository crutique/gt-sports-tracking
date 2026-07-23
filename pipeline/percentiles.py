"""Percentiles vs. the QUALIFIED pool, higher = better (Savant convention).

A player who is himself in the qualified pool is ranked among peers so the pool
leader reaches 100 and the tail reaches 0. A value not in the pool (a
non-qualified player, or the league average) is inserted with the midrank rule.
"""

HITTER_SLIDERS = ["ops", "avg", "obp", "slg", "kPct", "bbPct"]
PITCHER_SLIDERS = ["era", "whip", "kPct", "bbPct", "hr9", "oppAvg"]

_INVERTED = {
    "hitting": {"kPct"},
    "pitching": {"era", "whip", "bbPct", "hr9", "oppAvg"},
}


def is_inverted(side, metric):
    return metric in _INVERTED[side]


def midrank_percentile(pool, value, invert=False, in_pool=False):
    n = len(pool)
    if n == 0:
        return None
    below = sum(1 for x in pool if x < value)
    ties = sum(1 for x in pool if x == value)
    if in_pool and n > 1:
        # rank among peers: unique best -> 100, unique worst -> 0, ties averaged
        pct = (below + (ties - 1) / 2) / (n - 1) * 100
    else:
        # value inserted into the pool (non-qualified player, or league average)
        pct = (below + 0.5 * ties) / n * 100
    if invert:
        pct = 100 - pct
    return max(0, min(100, round(pct)))
