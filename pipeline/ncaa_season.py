"""Aggregate a team's NCAA games into canonical season rows.

Source split (see :mod:`pipeline.ncaa_api`), chosen from what each feed can
actually be trusted for:

* **``hittingSeason`` carries CUMULATIVE season-to-date figures**, so it is read
  as a *maximum* across a player's games — never summed. Summing multiplies the
  season (it once reported 114 HR for a 23-HR hitter). The max is exact and is
  immune to games missing from the schedule scan: it validated against NCAA's
  published leaderboards on AB/H/BB (6 of 6 players) and HR (3 of 3).
  But the feed is inconsistent — only ~5% of lines actually carry cumulative
  figures (the rest repeat the game line), and ``hittingSeason.strikeouts`` is
  **never** populated. So each counting stat is taken as
  ``max(cumulative_max, sum_of_game_lines)``: the cumulative value wins wherever
  it exists (exact, and includes games we never saw), while the per-game sum is a
  floor that still covers fields cumulative never fills, such as K.
* **Play-by-play** is the only feed carrying HBP / SF / SH.

Rows use the canonical keys the rest of the pipeline speaks
(:mod:`pipeline.stats_math`, :mod:`pipeline.college`).

**Identity resolution.** Scorer software differs per school *and per game*, so one
player arrives as ``('Vahn','Lackey')``, ``('','LACKEY')``, ``('','Lackey')`` and
``('','Vahn Lackey')`` in a single season; naive keying silently split one
player's season across several rows. Players are keyed by **surname**, with a
first initial appended only when the team truly has two of that surname. A
surname-only line on a team with two such players is unattributable and is
dropped rather than guessed.

**``g`` counts games with a batting line, so it can trail official G.** A game
whose box score never reached the feed (one of Georgia Tech's ACC-tournament
contests in 2026) is invisible here — GT's official G was 61 against 60 countable
games. The counting stats are unaffected, precisely because the cumulative line
already includes that game; only the appearance count is short. Prefer the rate
stats over ``g``-derived per-game figures where the two would disagree.

**HBP/SF completeness is reported, never assumed.** Play-by-play is absent for a
real slice of games (18 of Georgia Tech's 62 in 2026; ~17% D1-wide), so HBP/SF/SH
can be short. Rows carry ``pbpGames``/``games``/``eventsComplete`` so callers can
withhold the figures that depend on them (wOBA/wRC+) instead of publishing a
number that is quietly wrong. Note that **AVG/OBP/SLG/OPS/ISO/K%/BB% do not need
HBP** — OBP is reported cumulatively by the feed itself — so the standard slate
is exact regardless.
"""
import collections

from pipeline import ncaa_pbp as P

# cumulative hittingSeason field -> canonical key
_SEASON_MAP = {"atBats": "ab", "hits": "h", "walks": "bb", "strikeouts": "k",
               "runsScored": "r", "runsBattedIn": "rbi",
               "doubles": "d", "triples": "t", "homeRuns": "hr"}
# per-game batterStats field -> canonical key (no XBH breakdown on the game line)
_GAME_MAP = {"atBats": "ab", "hits": "h", "walks": "bb", "strikeouts": "k",
             "runsScored": "r", "runsBattedIn": "rbi"}
_COUNTING = tuple(_SEASON_MAP.values())


def _int(v):
    try:
        return int(str(v).strip().replace(",", "") or 0)
    except ValueError:
        return 0


def _pct(v):
    """Feed reports rates as '.519' or '51.9%'; return a float or None."""
    s = str(v or "").strip()
    if not s:
        return None
    try:
        return float(s.rstrip("%")) / 100 if s.endswith("%") else float(s)
    except ValueError:
        return None


def _team_box(box, team_id):
    for tb in box.get("teamBoxscore") or []:
        if _int(tb.get("teamId")) == int(team_id):
            return tb
    return None


def _batters(team_box):
    """Real batting lines only.

    The feed emits a ``batterStats`` block on **pitcher** rows too, but it is not
    a batting line -- it carries the opponent line, with ``atBats`` 0 alongside
    nonzero H/R/BB/K (impossible for a batter, since a strikeout is an at-bat).
    Aggregating those invented strikeouts wholesale: of 569 "batter" strikeouts
    across one Georgia Tech season, 514 came from such rows. A genuine two-way
    player is kept, because his line has real at-bats.
    """
    for p in (team_box or {}).get("playerStats") or []:
        bs = p.get("batterStats")
        if not bs:
            continue
        if p.get("pitcherStats") and _int(bs.get("atBats")) == 0:
            continue
        yield p


def resolve_identities(games, team_id):
    """Map every (first,last) variant seen this season to a stable player key."""
    variants = collections.Counter()
    for box, _ in games:
        for p in _batters(_team_box(box, team_id)):
            variants[P.split_packed_name(p.get("firstName"), p.get("lastName"))] += 1

    by_surname = collections.defaultdict(list)
    for (first, last), n in variants.items():
        by_surname[P._norm(last)].append((first, last))

    key_of, display = {}, {}
    for surname, entries in by_surname.items():
        initials = {P._norm(f)[:1] for f, _ in entries if P._norm(f)}
        ambiguous = len(initials) > 1
        for first, last in entries:
            ini = P._norm(first)[:1]
            if ambiguous and not ini:
                continue                      # unattributable -> never guess
            key = f"{surname}-{ini}" if ambiguous else surname
            key_of[(first, last)] = key
            cand = f"{first} {last}".strip()
            if len(cand) > len(display.get(key, "")):
                display[key] = cand
    return key_of, display


def _has_plays(pbp):
    for period in (pbp or {}).get("periods") or []:
        for half in period.get("playbyplayStats") or []:
            for play in half.get("plays") or []:
                if (play.get("playText") or "").strip():
                    return True
    return False


def team_season(games, team_id):
    """Canonical season rows for ``team_id`` from ``[(boxscore, pbp), ...]``."""
    key_of, display = resolve_identities(games, team_id)
    best = collections.defaultdict(collections.Counter)    # cumulative maxima
    totals = collections.defaultdict(collections.Counter)  # per-game sums (floor)
    events = collections.defaultdict(collections.Counter)
    appearances = collections.Counter()
    obp = {}
    pbp_games = 0

    for box, pbp in games:
        tb = _team_box(box, team_id)
        if not tb:
            continue
        for p in _batters(tb):
            key = key_of.get(P.split_packed_name(p.get("firstName"), p.get("lastName")))
            if key is None:
                continue
            appearances[key] += 1
            season = p.get("hittingSeason") or {}
            for src, dst in _SEASON_MAP.items():
                best[key][dst] = max(best[key][dst], _int(season.get(src)))
            for src, dst in _GAME_MAP.items():
                totals[key][dst] += _int(p["batterStats"].get(src))
            # OBP is reported cumulatively too; keep the one from the latest
            # (largest-AB) line so it matches the counting maxima
            v = _pct(season.get("onBasePercentage"))
            if v is not None and _int(season.get("atBats")) >= best[key]["ab"]:
                obp[key] = v

        if _has_plays(pbp):
            pbp_games += 1
            rosters = {_int(t["teamId"]): P.roster_from_boxscore(t)
                       for t in box.get("teamBoxscore") or []}
            for roster_key, tally in P.game_events(pbp, rosters).get(int(team_id), {}).items():
                key = _season_key_for(roster_key, key_of)
                if key is None:
                    continue
                for kind, n in tally.items():
                    events[key][kind] += n

    rows = []
    for key, c in best.items():
        row = {"stats_id": key, "name": display.get(key, key), "team": str(team_id),
               "g": appearances[key], "games": len(games), "pbpGames": pbp_games,
               "eventsComplete": pbp_games == len(games),
               "obpReported": obp.get(key)}
        # cumulative wins where it exists; the per-game sum is a floor and the
        # only source for fields cumulative never fills (K)
        row.update({k: max(c[k], totals[key][k]) for k in _COUNTING})
        row.update({"hbp": events[key][P.HBP], "sf": events[key][P.SF],
                    "sh": events[key][P.SH]})
        rows.append(row)
    return sorted(rows, key=lambda r: (-r["ab"], r["name"]))


def _season_key_for(roster_key, key_of):
    """'vahn-lackey' (per-game roster slug) -> the season identity key."""
    first, _, last = roster_key.partition("-")
    for (f, l), key in key_of.items():
        if P._norm(l) == last and P._norm(f) == first:
            return key
    for (f, l), key in key_of.items():          # line carried no first name
        if P._norm(l) == last:
            return key
    return None
