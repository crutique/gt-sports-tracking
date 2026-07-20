import json

import pytest

from pipeline import draft_status


def _fix(name):
    with open(f"pipeline/fixtures/draft/{name}") as f:
        return json.load(f)


@pytest.fixture
def api(monkeypatch):
    """Route draft_status._get to fixtures; unknown-person transactions are empty."""
    def fake_get(url):
        if "/draft/2026" in url:
            return _fix("draft_2026.json")
        if "playerId=702701" in url:
            return _fix("transactions_702701.json")
        if "/transactions" in url:
            return {"transactions": []}
        raise AssertionError(f"unexpected url {url}")
    monkeypatch.setattr(draft_status, "_get", fake_get)


def test_pick_fields_from_api(api):
    picks = draft_status.fetch_picks()
    lackey = picks[822518]
    assert lackey["round"] == "1" and lackey["pick"] == 3
    assert lackey["team"] == "Minnesota Twins" and lackey["slot"] == 9740100
    assert lackey["officialBonus"] is None and lackey["headshot"]
    assert picks[834497]["slot"] is None      # round-17 pickValue "0" must not surface as $0


def test_bonus_string_and_none():
    assert draft_status._bonus("10350000") == 10350000
    assert draft_status._bonus(10350000) == 10350000
    assert draft_status._bonus(None) is None
    assert draft_status._bonus("") is None


def test_signed_via_transaction(api):
    assert draft_status.fetch_signing(702701, "2026-07-20") == "2026-07-14"
    assert draft_status.fetch_signing(822518, "2026-07-20") is None


def test_status_resolution():
    s = draft_status._status
    assert s(signed=True, returning=False, today="2026-07-20", deadline="2026-07-27") == "signed"
    assert s(signed=False, returning=True, today="2026-07-20", deadline="2026-07-27") == "returning"
    assert s(signed=False, returning=False, today="2026-07-20", deadline="2026-07-27") == "unsigned"
    assert s(signed=False, returning=False, today="2026-07-28", deadline="2026-07-27") == "did_not_sign"
    # a declared returner stays "returning" after the deadline
    assert s(signed=False, returning=True, today="2026-07-28", deadline="2026-07-27") == "returning"


def test_build_draft_merges_curation(api):
    entries = [
        {"name": "Vahn Lackey", "person_id": 822518, "gt_role": "departing",
         "reported": {"bonus": 9500000, "source": "https://example.com/callis"}},
        {"name": "Isaiah Galason", "person_id": 834497, "gt_role": "signee",
         "slug": "isaiah-galason", "note": "insurance pick"},
        {"name": "Mason Patel", "gt_role": "departing",
         "udfa": {"team": "Athletics", "date": "2026-07-15", "source": "https://example.com/patel"}},
    ]
    out = draft_status.build_draft(entries, today="2026-07-20")
    lackey = next(p for p in out["players"] if p["name"] == "Vahn Lackey")
    assert lackey["bonus"] == 9500000 and lackey["bonusSource"] == "reported"
    assert lackey["reportedSourceUrl"] == "https://example.com/callis"
    assert lackey["status"] == "signed"            # a reported figure implies an agreed deal (label stays "reported" until official)
    galason = next(p for p in out["players"] if p["slug"] == "isaiah-galason")
    assert galason["status"] == "unsigned" and galason["note"] == "insurance pick"
    assert [p["name"] for p in out["udfa"]] == ["Mason Patel"]
    assert out["udfa"][0]["status"] == "signed_udfa"
    assert out["players"] == sorted(out["players"], key=lambda p: p["pick"])


def test_reported_bonus_implies_signed(api):
    entries = [{"name": "Carson Kerce", "person_id": 812668, "gt_role": "departing",
                "reported": {"bonus": 1900000, "source": "https://example.com/spotrac"}}]
    out = draft_status.build_draft(entries, today="2026-07-20")
    p = out["players"][0]
    assert p["status"] == "signed"
    assert p["bonus"] == 1900000 and p["bonusSource"] == "reported"
    assert p["signedDate"] is None


def test_official_bonus_beats_reported(api, monkeypatch):
    picks = draft_status.fetch_picks()
    monkeypatch.setattr(draft_status, "fetch_picks",
                        lambda year=2026: {822518: dict(picks[822518], officialBonus=9740100)})
    entries = [{"name": "Vahn Lackey", "person_id": 822518, "gt_role": "departing",
                "reported": {"bonus": 9500000, "source": "https://example.com"}}]
    out = draft_status.build_draft(entries, today="2026-07-20")
    p = out["players"][0]
    assert p["bonus"] == 9740100 and p["bonusSource"] == "official"
    assert p["status"] == "signed"                 # official bonus implies signed


def test_signed_transaction_sets_status_and_date(api):
    entries = [{"name": "Parker Brosius", "person_id": 702701, "gt_role": "departing"}]
    out = draft_status.build_draft(entries, today="2026-07-20")
    p = out["players"][0]
    assert p["status"] == "signed" and p["signedDate"] == "2026-07-14"
