import json
from pipeline import output

PLAYER_ASSIGNED = {"name": "Jackson Blakely", "slug": "jackson-blakely",
                   "gt_status": "returning", "player_type": "pitcher", "position": "P",
                   "summer": {"status": "assigned", "team": "Willmar Stingers",
                              "league": "northwoods", "stats_id": "jackson-blakely"}}
PLAYER_UNASSIGNED = {"name": "Will Baker", "slug": "will-baker", "gt_status": "returning",
                     "player_type": "hitter", "position": "", "class2027": "JR",
                     "summer": {"status": "unassigned"}, "recruit": {"hometown": "X"}}
LEAGUES = {"northwoods": {"name": "Northwoods League", "abbrev": "NWL",
                          "official_url": "https://northwoodsleague.com",
                          "platform": "fixture", "tier": 1}}
BUNDLE = {"jackson-blakely": {
    "hitting": None,
    "pitching": {"counting": {"g": 7, "ip": "37.1"}, "rates": {"era": 2.65},
                 "sliders": [{"metric": "era", "value": 2.65, "percentile": 80,
                              "leagueAvg": 4.10, "derived": False}]},
    "gamelog": [{"date": "2026-07-12", "opponent": "vs Madison", "ip_outs": 18,
                 "h": 4, "r": 2, "er": 2, "bb": 1, "k": 7, "hr": 1, "dec": "W"}]}}


def test_assemble_assigned_with_stats():
    recs = output.assemble([PLAYER_ASSIGNED, PLAYER_UNASSIGNED], LEAGUES,
                           {"northwoods": BUNDLE}, previous={}, today="2026-07-14")
    by_slug = {r["slug"]: r for r in recs}
    jb = by_slug["jackson-blakely"]
    assert jb["asOf"] == "2026-07-14"
    assert jb["gtStatus"] == "returning" and jb["playerType"] == "pitcher"
    assert jb["summer"] == {"status": "assigned", "team": "Willmar Stingers",
                            "leagueKey": "northwoods"}
    assert jb["pitching"]["sliders"][0]["percentile"] == 80
    assert jb["classYear"] == ""
    wb = by_slug["will-baker"]
    assert wb["summer"]["status"] == "unassigned"
    assert wb["hitting"] is None and wb["asOf"] is None
    assert wb["classYear"] == "JR"
    assert wb["recruit"] == {"hometown": "X"}
    assert jb["recruit"] is None


def test_assemble_note_passthrough():
    noted = {**PLAYER_ASSIGNED,
             "summer": {**PLAYER_ASSIGNED["summer"],
                        "note": "Signed with Willmar in February but has not appeared."}}
    noted_unassigned = {**PLAYER_UNASSIGNED,
                        "summer": {"status": "unassigned",
                                   "note": "Held out of summer ball for the MLB Draft."}}
    recs = output.assemble([noted, noted_unassigned], LEAGUES, {"northwoods": BUNDLE},
                           previous={}, today="2026-07-14")
    by_slug = {r["slug"]: r for r in recs}
    assert by_slug["jackson-blakely"]["note"] == \
        "Signed with Willmar in February but has not appeared."
    assert by_slug["will-baker"]["note"] == "Held out of summer ball for the MLB Draft."


def test_assemble_note_absent_is_none():
    recs = output.assemble([PLAYER_ASSIGNED, PLAYER_UNASSIGNED], LEAGUES,
                           {"northwoods": BUNDLE}, previous={}, today="2026-07-14")
    assert all(r["note"] is None for r in recs)


def test_assemble_carries_forward_on_missing_bundle():
    prev_rec = {"slug": "jackson-blakely", "asOf": "2026-07-13", "summer":
                {"status": "assigned", "team": "Willmar Stingers", "leagueKey": "northwoods"},
                "pitching": {"counting": {"g": 6}}, "hitting": None}
    recs = output.assemble([PLAYER_ASSIGNED], LEAGUES, {}, previous=
                           {"jackson-blakely": prev_rec}, today="2026-07-14")
    assert recs[0]["asOf"] == "2026-07-13"          # kept yesterday's stamp
    assert recs[0]["pitching"]["counting"]["g"] == 6


def test_write_outputs(tmp_path):
    recs = output.assemble([PLAYER_ASSIGNED], LEAGUES, {"northwoods": BUNDLE},
                           previous={}, today="2026-07-14")
    out, hist = tmp_path / "data", tmp_path / "history"
    output.write_outputs(recs, LEAGUES, {"jackson-blakely": BUNDLE["jackson-blakely"]["gamelog"]},
                         out, hist, today="2026-07-14")
    players = json.loads((out / "players.json").read_text())
    assert players[0]["slug"] == "jackson-blakely"
    leagues = json.loads((out / "leagues.json").read_text())
    assert leagues[0]["gtPlayers"] == ["jackson-blakely"]
    log = json.loads((out / "gamelogs" / "jackson-blakely.json").read_text())
    assert log[0]["dec"] == "W"
    assert (hist / "2026-07-14" / "players.json").exists()


def test_load_previous_roundtrip(tmp_path):
    recs = output.assemble([PLAYER_ASSIGNED], LEAGUES, {"northwoods": BUNDLE},
                           previous={}, today="2026-07-14")
    out = tmp_path / "data"
    output.write_outputs(recs, LEAGUES, {}, out, tmp_path / "h", today="2026-07-14")
    prev = output.load_previous(out)
    assert prev["jackson-blakely"]["asOf"] == "2026-07-14"


def test_load_previous_missing_dir(tmp_path):
    assert output.load_previous(tmp_path / "nope") == {}


def test_load_previous_corrupted_returns_empty(tmp_path):
    out = tmp_path / "data"
    out.mkdir()
    (out / "players.json").write_text("{truncated")
    assert output.load_previous(out) == {}


def test_write_meta_stamps_generated_at(tmp_path):
    from pipeline import output
    output.write_meta(str(tmp_path), "draft-watch")
    import json, datetime
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["source"] == "draft-watch"
    datetime.datetime.fromisoformat(meta["generatedAt"])  # parses
