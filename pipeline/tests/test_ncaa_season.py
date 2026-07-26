"""Season aggregation: identity resolution + canonical rows from cumulative lines."""
from pipeline import ncaa_season as S


def _game(team_id, players, plays=()):
    box = {
        "teams": [{"teamId": str(team_id), "seoname": "georgia-tech"}],
        "teamBoxscore": [{"teamId": team_id, "playerStats": players}],
    }
    pbp = {"periods": [{"periodNumber": 1, "playbyplayStats": [
        {"teamId": team_id, "plays": [{"playText": t} for t in plays]}]}]}
    return box, pbp


def _bat(first, last, game=None, **season):
    """A player line. ``season`` values are CUMULATIVE season-to-date (as the feed
    reports them on the ~5% of lines that carry them); ``game`` is this game's
    ``batterStats``."""
    hs = {"atBats": 0, "hits": 0, "walks": 0, "strikeouts": 0, "runsScored": 0,
          "runsBattedIn": 0, "doubles": 0, "triples": 0, "homeRuns": 0}
    hs.update(season)
    return {"firstName": first, "lastName": last,
            "batterStats": {k: str(v) for k, v in (game or {"atBats": 1}).items()},
            "hittingSeason": {k: str(v) for k, v in hs.items()}}


# --- the core correctness property -----------------------------------------
def test_uses_cumulative_max_not_a_sum():
    # hittingSeason is season-to-date; summing it multiplies a player's season
    # (a real bug this caught: 114 HR reported for a 23-HR hitter)
    games = [
        _game(1, [_bat("Ryan", "Zuckerman", atBats=100, hits=30, homeRuns=10)]),
        _game(1, [_bat("Ryan", "Zuckerman", atBats=180, hits=55, homeRuns=18)]),
        _game(1, [_bat("Ryan", "Zuckerman", atBats=210, hits=66, homeRuns=23)]),
    ]
    r = S.team_season(games, team_id=1)[0]
    assert (r["ab"], r["h"], r["hr"]) == (210, 66, 23)


def test_out_of_order_games_still_yield_the_season_total():
    games = [
        _game(1, [_bat("Ryan", "Zuckerman", atBats=210, homeRuns=23)]),
        _game(1, [_bat("Ryan", "Zuckerman", atBats=100, homeRuns=10)]),
    ]
    assert S.team_season(games, team_id=1)[0]["hr"] == 23


def test_strikeouts_come_from_game_lines_since_cumulative_never_fills_them():
    # hittingSeason.strikeouts is always 0 in the real feed; K must come from the
    # per-game batterStats sum or K% would silently read 0.000 for everyone
    games = [
        _game(1, [_bat("V", "Lackey", game={"atBats": 4, "strikeouts": 2}, atBats=100)]),
        _game(1, [_bat("V", "Lackey", game={"atBats": 3, "strikeouts": 1}, atBats=180)]),
    ]
    r = S.team_season(games, team_id=1)[0]
    assert r["k"] == 3
    assert r["ab"] == 180, "cumulative still wins for AB"


def test_cumulative_wins_over_a_short_game_sum():
    # the per-game sum is only a floor: it misses games absent from the feed
    games = [_game(1, [_bat("V", "Lackey", game={"atBats": 4}, atBats=219)])]
    assert S.team_season(games, team_id=1)[0]["ab"] == 219


def test_canonical_keys_present():
    games = [_game(1, [_bat("V", "Lackey", atBats=219, hits=87, walks=50,
                            strikeouts=30, runsScored=60, runsBattedIn=70,
                            doubles=20, triples=1, homeRuns=20)])]
    r = S.team_season(games, team_id=1)[0]
    for k in ("ab", "h", "bb", "k", "r", "rbi", "d", "t", "hr", "hbp", "sf", "sh"):
        assert k in r
    assert (r["ab"], r["h"], r["bb"], r["d"], r["hr"]) == (219, 87, 50, 20, 20)


# --- identity resolution ----------------------------------------------------
def test_same_player_across_all_real_name_variants_is_one_identity():
    games = [
        _game(1, [_bat("Vahn", "Lackey", atBats=10)]),
        _game(1, [_bat("", "LACKEY", atBats=20)]),
        _game(1, [_bat("", "Lackey", atBats=30)]),
        _game(1, [_bat("", "Vahn Lackey", atBats=40)]),
    ]
    rows = S.team_season(games, team_id=1)
    assert len(rows) == 1
    assert rows[0]["ab"] == 40 and rows[0]["name"] == "Vahn Lackey"
    assert rows[0]["g"] == 4


def test_two_players_sharing_a_surname_stay_separate():
    games = [
        _game(1, [_bat("Zack", "Williams", atBats=30), _bat("Adam", "Williams", atBats=50)]),
        _game(1, [_bat("Zack", "Williams", atBats=40), _bat("Adam", "Williams", atBats=55)]),
    ]
    rows = {r["name"]: r for r in S.team_season(games, team_id=1)}
    assert rows["Zack Williams"]["ab"] == 40 and rows["Adam Williams"]["ab"] == 55


def test_surname_only_row_is_dropped_when_the_surname_is_ambiguous():
    games = [
        _game(1, [_bat("Zack", "Williams", atBats=30), _bat("Adam", "Williams", atBats=50)]),
        _game(1, [_bat("", "Williams", atBats=99)]),
    ]
    rows = {r["name"]: r for r in S.team_season(games, team_id=1)}
    assert rows["Zack Williams"]["ab"] == 30 and rows["Adam Williams"]["ab"] == 50
    assert 99 not in [r["ab"] for r in rows.values()], "never guess between real people"


# --- PBP-sourced events + honesty about their completeness ------------------
def test_pulls_hbp_and_sf_from_play_by_play():
    games = [
        _game(1, [_bat("Vahn", "Lackey", atBats=10)], plays=["Lackey, V. hit by pitch (1-0 B)"]),
        _game(1, [_bat("Vahn", "Lackey", atBats=20)], plays=["Vahn Lackey flied out to lf, SF, RBI"]),
    ]
    r = S.team_season(games, team_id=1)[0]
    assert r["hbp"] == 1 and r["sf"] == 1
    assert r["eventsComplete"] is True


def test_partial_pbp_coverage_is_reported_not_hidden():
    # 18 of GT's 62 games had no play-by-play, so HBP/SF can be short; callers must
    # be able to withhold HBP-dependent figures (OBP/OPS/wOBA) rather than publish
    # a number that is quietly wrong
    games = [
        _game(1, [_bat("Vahn", "Lackey", atBats=10)], plays=["Lackey, V. hit by pitch"]),
        _game(1, [_bat("Vahn", "Lackey", atBats=20)], plays=[]),
    ]
    r = S.team_season(games, team_id=1)[0]
    assert r["pbpGames"] == 1 and r["games"] == 2
    assert r["eventsComplete"] is False
