from pipeline import name_watch


def _row(sid, name, team="Orleans Firebirds"):
    return {"stats_id": sid, "name": name, "team": team}


def _player(name, slug, summer):
    return {"name": name, "slug": slug, "gt_status": "transfer", "summer": summer}


def test_unassigned_registry_name_in_pool_warns():
    players = [_player("Jayden Stroman", "jayden-stroman", {"status": "unassigned"})]
    tables = {"batting": [], "pitching": [_row("815875", "Jayden Stroman")]}
    warnings = name_watch.check_names("cape_cod", tables, players)
    assert warnings == [
        "name-watch: 'Jayden Stroman' (registry: unassigned) matches cape_cod "
        "pitching row stats_id=815875 team='Orleans Firebirds' "
        "— possible missing assignment"
    ]


def test_batting_side_reported():
    players = [_player("Patrick Walsh", "patrick-walsh", {"status": "unassigned"})]
    tables = {"batting": [_row("844027", "Patrick Walsh", team="Johnson City Doughboys")],
              "pitching": []}
    warnings = name_watch.check_names("appalachian", tables, players)
    assert len(warnings) == 1
    w = warnings[0]
    assert "appalachian batting row" in w
    assert "stats_id=844027" in w
    assert "team='Johnson City Doughboys'" in w
    assert "possible missing assignment" in w


def test_assigned_elsewhere_warns():
    players = [_player("Jayden Stroman", "jayden-stroman",
                       {"status": "assigned", "league": "northwoods",
                        "team": "Willmar Stingers", "stats_id": "10999"})]
    tables = {"batting": [], "pitching": [_row("815875", "Jayden Stroman")]}
    warnings = name_watch.check_names("cape_cod", tables, players)
    assert len(warnings) == 1
    assert "assigned to northwoods" in warnings[0]
    assert "possible missing assignment" in warnings[0]


def test_id_mismatch_in_same_league_warns():
    players = [_player("Jayden Stroman", "jayden-stroman",
                       {"status": "assigned", "league": "cape_cod",
                        "team": "Orleans Firebirds", "stats_id": "999999"})]
    tables = {"batting": [], "pitching": [_row("815875", "Jayden Stroman")]}
    warnings = name_watch.check_names("cape_cod", tables, players)
    assert len(warnings) == 1
    assert "stats_id mismatch" in warnings[0]
    assert "999999" in warnings[0] and "815875" in warnings[0]


def test_same_league_same_id_no_warning():
    players = [_player("Jayden Stroman", "jayden-stroman",
                       {"status": "assigned", "league": "cape_cod",
                        "team": "Orleans Firebirds", "stats_id": "815875"})]
    tables = {"batting": [], "pitching": [_row("815875", "Jayden Stroman")]}
    assert name_watch.check_names("cape_cod", tables, players) == []


def test_int_vs_str_stats_id_still_matches():
    players = [_player("Jayden Stroman", "jayden-stroman",
                       {"status": "assigned", "league": "cape_cod",
                        "team": "Orleans Firebirds", "stats_id": 815875})]
    tables = {"batting": [], "pitching": [_row("815875", "Jayden Stroman")]}
    assert name_watch.check_names("cape_cod", tables, players) == []


def test_unrelated_names_no_warning():
    players = [_player("Jayden Stroman", "jayden-stroman", {"status": "unassigned"}),
               _player("Patrick Walsh", "patrick-walsh", {"status": "unassigned"})]
    tables = {"batting": [_row("1", "Random Hitter"), _row("2", "Another Guy")],
              "pitching": [_row("3", "Some Pitcher")]}
    assert name_watch.check_names("cape_cod", tables, players) == []


def test_name_match_is_case_period_and_whitespace_insensitive():
    players = [_player("J.T. Smith", "jt-smith", {"status": "unassigned"})]
    tables = {"batting": [_row("42", "JT  SMITH")], "pitching": []}
    warnings = name_watch.check_names("cape_cod", tables, players)
    assert len(warnings) == 1
    assert "'J.T. Smith'" in warnings[0]


def test_no_substring_matching():
    # Surname-only / partial overlap must NOT match — exact full-name only.
    players = [_player("Jayden Stroman", "jayden-stroman", {"status": "unassigned"})]
    tables = {"batting": [_row("7", "Marcus Stroman"), _row("8", "Jayden Stroman Jr")],
              "pitching": []}
    assert name_watch.check_names("cape_cod", tables, players) == []


def test_not_playing_status_shown_in_message():
    players = [_player("Jayden Stroman", "jayden-stroman", {"status": "not_playing"})]
    tables = {"batting": [], "pitching": [_row("815875", "Jayden Stroman")]}
    warnings = name_watch.check_names("cape_cod", tables, players)
    assert len(warnings) == 1
    assert "(registry: not_playing)" in warnings[0]


def test_rows_without_names_are_skipped():
    players = [_player("Jayden Stroman", "jayden-stroman", {"status": "unassigned"})]
    tables = {"batting": [{"stats_id": "1", "team": "X"}],
              "pitching": [{"stats_id": "2", "name": "", "team": "Y"}]}
    assert name_watch.check_names("cape_cod", tables, players) == []


def test_missing_table_side_tolerated():
    players = [_player("Jayden Stroman", "jayden-stroman", {"status": "unassigned"})]
    tables = {"pitching": [_row("815875", "Jayden Stroman")]}
    warnings = name_watch.check_names("cape_cod", tables, players)
    assert len(warnings) == 1
