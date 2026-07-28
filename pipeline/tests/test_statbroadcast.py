"""StatBroadcast archive client -- enumeration and sport discrimination.

Network calls are not exercised here; the S3 listing shape and the
baseball/softball discriminator are, because both are assumptions the backfill
rests on and both would fail silently.
"""
from pathlib import Path

import pytest

from pipeline import statbroadcast as SB
from pipeline import statcrew

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "statcrew" / \
    "ucdavis_at_texas_2026-02-15.xml"

# A real ListBucketResult page, trimmed. Keys are `{sbid}.{ext}` and the cursor
# is the last key seen -- there is no date or per-school index, so this listing
# is the only way to enumerate the archive.
_LISTING = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>archive.statbroadcast.com</Name><MaxKeys>1000</MaxKeys>
  <IsTruncated>false</IsTruncated>
  <Contents><Key>651570.xml</Key>
    <LastModified>2026-02-15T23:14:02.000Z</LastModified><Size>55910</Size></Contents>
  <Contents><Key>651570.pdf</Key>
    <LastModified>2026-02-15T23:14:03.000Z</LastModified><Size>209306</Size></Contents>
  <Contents><Key>1.xml.orig</Key>
    <LastModified>2019-09-03T19:25:57.000Z</LastModified><Size>140922</Size></Contents>
</ListBucketResult>"""


def test_listing_yields_key_date_and_size(monkeypatch):
    monkeypatch.setattr(SB, "_get", lambda url, timeout=None: _LISTING.encode())
    rows = list(SB.list_objects())
    assert rows[0] == ("651570.xml", "2026-02-15", 55910)
    assert len(rows) == 3


def test_listing_stops_when_not_truncated(monkeypatch):
    calls = []

    def fake(url, timeout=None):
        calls.append(url)
        return _LISTING.encode()

    monkeypatch.setattr(SB, "_get", fake)
    list(SB.list_objects())
    assert len(calls) == 1, "must not keep paging past IsTruncated=false"


def test_sbid_extraction_ignores_non_numeric_keys():
    assert SB.sbid_of("651570.xml") == "651570"
    assert SB.sbid_of("651570.xml.orig") == "651570"
    assert SB.sbid_of(".html") is None
    assert SB.sbid_of("index.html") is None


def test_xml_url_is_the_raw_statcrew_file():
    assert SB.xml_url("651570") == "http://archive.statbroadcast.com/651570.xml"


def test_missing_object_is_a_gap_not_an_error(monkeypatch):
    import urllib.error

    def gone(url, timeout=None):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(SB, "_get", gone)
    assert SB.fetch_xml("999999999", cache=False) is None


# --- baseball vs softball ---------------------------------------------------
def test_baseball_is_identified_by_scheduled_innings():
    game = statcrew.parse_game(FIXTURE.read_text(encoding="utf-8", errors="ignore"))
    assert game["sched_innings"] == 9
    assert SB.is_baseball(game) is True


def test_softball_is_excluded():
    # same `bsgame` root, same scorer software -- only schedinn separates them
    assert SB.is_baseball({"sched_innings": 7, "plays": []}) is False


def test_falls_back_to_innings_played_when_schedinn_is_absent():
    # some older archived files omit schedinn entirely
    assert SB.is_baseball({"sched_innings": 0,
                           "plays": [{"inning": 9}, {"inning": 3}]}) is True
    assert SB.is_baseball({"sched_innings": 0,
                           "plays": [{"inning": 7}, {"inning": 2}]}) is False


def test_sha256_is_stable_for_provenance():
    assert SB.sha256("abc") == SB.sha256("abc")
    assert len(SB.sha256("abc")) == 64
