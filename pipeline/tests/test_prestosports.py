import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from pipeline.scrapers import SCRAPERS, prestosports

FIX = Path("pipeline/fixtures/prestosports_necbl")
SB_FIX = Path("pipeline/fixtures/prestosports_sunbelt")

NECBL_CFG = {
    "name": "New England Collegiate Baseball League", "abbrev": "NECBL",
    "official_url": "https://necbl.com", "platform": "prestosports",
    "site_base": "https://necbl.com", "sport_path": "sports/bsb",
    "season": "2026", "tier": 1,
}
SUNBELT_CFG = {
    "name": "Sunbelt Baseball League", "abbrev": "SBL",
    "official_url": "https://www.sunbeltbaseballleague.net", "platform": "prestosports",
    "site_base": "https://www.sunbeltbaseballleague.net", "sport_path": "sports/bsb",
    "season": "2026", "tier": 1, "request_delay_s": 9.5,
}

BAT_KEYS = {"stats_id", "name", "team", "g", "ab", "r", "h", "d", "t", "hr",
            "rbi", "bb", "k", "hbp", "sb", "cs", "sf", "sh", "pa"}
PIT_KEYS = {"stats_id", "name", "team", "g", "gs", "ip_outs", "w", "l", "sv",
            "hld", "h", "r", "er", "bb", "k", "hb", "hr", "bf"}
HIT_GAME_KEYS = {"date", "opponent", "ab", "r", "h", "d", "t", "hr", "rbi", "bb", "k", "sb"}
PIT_GAME_KEYS = {"date", "opponent", "ip_outs", "h", "r", "er", "bb", "k", "hr", "dec"}


def _http_error(code):
    resp = requests.Response()
    resp.status_code = code
    return requests.HTTPError(response=resp)


def _url_key(url):
    """(kind, pos, start) for players lists; ('player', slug, None) for player pages."""
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    m = re.search(r"/players/([^/?]+)$", parsed.path)
    if m:
        return ("player", m.group(1), None)
    assert parsed.path.endswith("/players")
    return ("list", q["pos"][0], int(q.get("start", ["0"])[0]))


def _fake_site(monkeypatch, routes, fix=FIX):
    """Route _get_html by URL; record requests; neuter sleeps. Returns request log."""
    calls = []

    def fake(url):
        calls.append(url)
        target = routes.get(_url_key(url))
        if target is None:
            raise _http_error(404)
        if isinstance(target, int):
            raise _http_error(target)
        return (fix / target).read_text()

    monkeypatch.setattr(prestosports, "_get_html", fake)
    monkeypatch.setattr(prestosports.time, "sleep", lambda s: None)
    return calls


NECBL_ROUTES = {
    ("list", "h", 0): "players_h_1.html",
    ("list", "h", 5): "players_h_2.html",
    ("list", "h", 10): "players_empty.html",
    ("list", "p", 0): "players_p_1.html",
    ("player", "elistephensv8er", None): "gamelog_elistephensv8er.html",
    ("player", "jackensellhzak", None): "gamelog_jackensellhzak.html",
}

SB_ROUTES = {
    ("list", "h", 0): "players_h_1.html",
    ("list", "h", 5): 500,       # AWS WAF site: offsets past the end return HTTP 500
    ("list", "p", 0): "players_p_1.html",
    ("player", "kolbymartinch2v", None): "gamelog_kolbymartinch2v.html",
}


@pytest.fixture(autouse=True)
def small_pages(monkeypatch):
    """Fixture pages hold 4-5 rows; shrink the platform page size to match."""
    monkeypatch.setattr(prestosports, "_PAGE_SIZE", 5)


def test_registered():
    assert SCRAPERS["prestosports"] is prestosports


def test_league_stats_normalized(monkeypatch):
    _fake_site(monkeypatch, NECBL_ROUTES)
    stats = prestosports.fetch_league_stats(NECBL_CFG)
    assert set(stats["batting"][0]) == BAT_KEYS
    assert set(stats["pitching"][0]) == PIT_KEYS
    # 5 + 5 rows over two pages, minus the never-appeared player (gp '-')
    ids = {r["stats_id"] for r in stats["batting"]}
    assert len(stats["batting"]) == 9 and "ajaschettinovebm" not in ids
    eli = next(r for r in stats["batting"] if r["stats_id"] == "elistephensv8er")
    assert eli == {"stats_id": "elistephensv8er", "name": "E Stephens",
                   "team": "Keene Swamp Bats", "g": 22, "ab": 83, "r": 13, "h": 18,
                   "d": 2, "t": 0, "hr": 1, "rbi": 6, "bb": 13, "k": 32, "hbp": 3,
                   "sb": 0, "cs": 0, "sf": 0, "sh": 0, "pa": 99}
    # r / sb / cs merged in from the separate baserunning table
    zamp = next(r for r in stats["batting"] if r["stats_id"] == "nickzampieronixle")
    assert zamp["r"] == 13 and zamp["sb"] == 13 and zamp["cs"] == 1
    # pitching pool: zero-appearance row (two-way hitter, app 0) filtered out
    pit_ids = {r["stats_id"] for r in stats["pitching"]}
    assert pit_ids == {"jackensellhzak", "jonasaponickeozi", "thomasgalusha6wfq"}
    ensell = next(r for r in stats["pitching"] if r["stats_id"] == "jackensellhzak")
    assert ensell == {"stats_id": "jackensellhzak", "name": "J Ensell",
                      "team": "Valley Blue Sox", "g": 9, "gs": 0, "ip_outs": 40,
                      "w": 1, "l": 1, "sv": 4, "hld": 0, "h": 4, "r": 4, "er": 0,
                      "bb": 2, "k": 28, "hb": 5, "hr": 0, "bf": 49}
    assert all(isinstance(r["stats_id"], str) for r in stats["batting"])


def test_pagination_stops_on_empty_page(monkeypatch):
    calls = _fake_site(monkeypatch, NECBL_ROUTES)
    prestosports.fetch_league_stats(NECBL_CFG)
    lists = [_url_key(u) for u in calls if _url_key(u)[0] == "list"]
    # hitting sweep walks 0 -> 5 -> 10 (empty page ends it); a 4-row pitching
    # page is already partial, so no second pitching request is made
    assert lists == [("list", "h", 0), ("list", "h", 5), ("list", "h", 10),
                     ("list", "p", 0)]


def test_pagination_stops_on_repeated_page(monkeypatch):
    routes = dict(NECBL_ROUTES)
    routes[("list", "h", 10)] = "players_h_2.html"   # clamped repeat, no new players
    calls = _fake_site(monkeypatch, routes)
    stats = prestosports.fetch_league_stats(NECBL_CFG)
    assert len(stats["batting"]) == 9
    assert ("list", "h", 15) not in [_url_key(u) for u in calls]


def test_league_error_raises(monkeypatch):
    _fake_site(monkeypatch, {("list", "h", 0): 500})
    with pytest.raises(requests.HTTPError):
        prestosports.fetch_league_stats(NECBL_CFG)


def test_iso_date_forms():
    assert prestosports._iso_date("Jun 4", 2026) == "2026-06-04"
    assert prestosports._iso_date("May 30", 2026) == "2026-05-30"
    assert prestosports._iso_date("Jul 13 #", 2026) == "2026-07-13"


def test_game_logs(monkeypatch):
    _fake_site(monkeypatch, NECBL_ROUTES)
    logs = prestosports.fetch_game_logs(
        NECBL_CFG, ["elistephensv8er", "jackensellhzak", "eli-stephens", "missingxyz"])
    assert logs["eli-stephens"] == []      # registry placeholder -> 404 -> empty
    assert logs["missingxyz"] == []
    eli = logs["elistephensv8er"]
    dates = [g["date"] for g in eli]
    assert dates == sorted(dates, reverse=True) and all(d.startswith("2026-") for d in dates)
    # schedule rows he didn't play in and future games are dropped; the
    # '#'-dated non-league game (Jul 13 at Nashua) is excluded too
    assert "2026-07-13" not in dates and "2026-06-04" not in dates
    assert "2026-06-06" not in dates and "2026-07-16" not in dates
    assert len(eli) == 6
    assert eli[0] == {"date": "2026-07-14", "opponent": "at Mystic Schooners",
                      "ab": 5, "r": 0, "h": 1, "d": 0, "t": 0, "hr": 0,
                      "rbi": 0, "bb": 0, "k": 1, "sb": 0}
    # Jul 12 doubleheader: two hitting entries plus a mop-up pitching outing
    jul12 = [g for g in eli if g["date"] == "2026-07-12"]
    hit12 = [g for g in jul12 if "ab" in g]
    pit12 = [g for g in jul12 if "ip_outs" in g]
    assert len(hit12) == 2 and {g["h"] for g in hit12} == {0, 1}
    assert all(set(g) == HIT_GAME_KEYS for g in hit12)
    assert pit12 == [{"date": "2026-07-12", "opponent": "vs Ocean State Waves",
                      "ip_outs": 12, "h": 3, "r": 1, "er": 1, "bb": 0, "k": 0,
                      "hr": 0, "dec": ""}]
    jun9 = next(g for g in eli if g["date"] == "2026-06-09")
    assert jun9["opponent"] == "vs Upper Valley Nighthawks"
    assert jun9["ab"] == 4 and jun9["h"] == 2 and jun9["d"] == 1 and jun9["k"] == 2

    ensell = logs["jackensellhzak"]
    # pure reliever: zero-PA hitting rows yield no batting entries
    assert all(set(g) == PIT_GAME_KEYS for g in ensell)
    assert [g["date"] for g in ensell] == ["2026-07-09", "2026-07-01",
                                           "2026-06-24", "2026-06-04"]
    assert [g["dec"] for g in ensell] == ["", "W", "L", ""]
    assert ensell[0]["ip_outs"] == 4                     # '1.1' innings
    jun24 = ensell[2]
    assert jun24["h"] == 2 and jun24["r"] == 4 and jun24["er"] == 0


def test_sunbelt_league_stats_config_driven(monkeypatch):
    calls = _fake_site(monkeypatch, SB_ROUTES, fix=SB_FIX)
    stats = prestosports.fetch_league_stats(SUNBELT_CFG)
    # a full first page forces a probe at start=5; the site answers HTTP 500
    # past the last row, which ends the sweep instead of failing the league
    assert ("list", "h", 5) in [_url_key(u) for u in calls]
    assert len(stats["batting"]) == 5
    kolby = next(r for r in stats["batting"] if r["stats_id"] == "kolbymartinch2v")
    assert kolby == {"stats_id": "kolbymartinch2v", "name": "K Martin",
                     "team": "Brookhaven Bucks", "g": 9, "ab": 27, "r": 5, "h": 4,
                     "d": 0, "t": 0, "hr": 0, "rbi": 3, "bb": 5, "k": 3, "hbp": 1,
                     "sb": 5, "cs": 0, "sf": 0, "sh": 0, "pa": 33}
    dimitri = next(r for r in stats["pitching"] if r["stats_id"] == "dimitriangelakos382f")
    assert dimitri == {"stats_id": "dimitriangelakos382f", "name": "D Angelakos",
                       "team": "Brookhaven Bucks", "g": 1, "gs": 0, "ip_outs": 9,
                       "w": 0, "l": 1, "sv": 0, "hld": 0, "h": 5, "r": 5, "er": 5,
                       "bb": 1, "k": 6, "hb": 0, "hr": 2, "bf": 15}
    assert all(r["g"] > 0 for r in stats["pitching"])


def test_sunbelt_game_logs(monkeypatch):
    _fake_site(monkeypatch, SB_ROUTES, fix=SB_FIX)
    logs = prestosports.fetch_game_logs(SUNBELT_CFG, ["kolbymartinch2v"])
    kolby = logs["kolbymartinch2v"]
    assert len(kolby) == 5                              # Jun 19 DNP row dropped
    assert kolby[0]["date"] == "2026-06-17"
    assert [g["date"] for g in kolby].count("2026-05-30") == 2   # doubleheader
    assert [g["date"] for g in kolby].count("2026-06-10") == 2
    assert all(g["opponent"] in ("vs Oconee Wild Things", "at Oconee Wild Things",
                                 "vs Gainesville GolDiggers") for g in kolby)
    assert sum(g["sb"] for g in kolby) == 4             # 5th steal is outside the trim
    jun10_g2 = [g for g in kolby if g["date"] == "2026-06-10"][1]
    assert jun10_g2["ab"] == 2 and jun10_g2["rbi"] == 2 and jun10_g2["sb"] == 2


def _fake_requests_get(monkeypatch, statuses, body=b""):
    """Replace requests.get with canned responses; capture calls and sleeps."""
    calls, sleeps = [], []
    seq = iter(statuses)

    def fake(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers or {}, "timeout": timeout})
        resp = requests.Response()
        resp.status_code = next(seq)
        resp._content = body
        resp.url = url
        return resp

    monkeypatch.setattr(prestosports.requests, "get", fake)
    monkeypatch.setattr(prestosports.time, "sleep", lambda s: sleeps.append(s))
    return calls, sleeps


def test_browser_user_agent_sent(monkeypatch):
    body = (FIX / "players_empty.html").read_bytes()
    calls, _ = _fake_requests_get(monkeypatch, [200, 200], body=body)
    prestosports.fetch_league_stats(NECBL_CFG)
    assert calls, "no HTTP requests made"
    for c in calls:
        # default python/curl UAs get 403 from these sites — must look like a browser
        assert c["headers"]["User-Agent"].startswith("Mozilla/5.0")


def test_waf_challenge_202_retried_not_parsed(monkeypatch):
    body = (FIX / "players_empty.html").read_bytes()
    calls, sleeps = _fake_requests_get(monkeypatch, [202, 202, 200, 200], body=body)
    stats = prestosports.fetch_league_stats(NECBL_CFG)
    assert stats == {"batting": [], "pitching": []}     # parsed from the 200s only
    assert len(calls) == 4                              # 2 challenges + 2 sweeps
    assert sleeps and sleeps[0] > 0                     # backed off between retries


def test_waf_challenge_202_persistent_raises(monkeypatch):
    _fake_requests_get(monkeypatch, [202] * 20, body=b"challenge.js stub")
    with pytest.raises(requests.HTTPError):
        prestosports.fetch_league_stats(NECBL_CFG)


def test_request_delay_from_config(monkeypatch):
    body = (SB_FIX / "players_p_1.html").read_bytes()
    _, sleeps = _fake_requests_get(monkeypatch, [200] * 10, body=body)
    prestosports.fetch_league_stats(SUNBELT_CFG)
    assert 9.5 in sleeps                                # honors request_delay_s
