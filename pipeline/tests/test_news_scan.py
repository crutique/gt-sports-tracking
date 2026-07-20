from pathlib import Path

from pipeline import news_scan

FIX = Path("pipeline/fixtures/newswatch")

TODAY = "2026-07-21"


# ---------------------------------------------------------------------------
# decide() -- pure policy matrix
# ---------------------------------------------------------------------------

def test_decide_whitelisted_signed_is_reported():
    extraction = {"event": "signed", "amount": 1900000,
                  "source_url": "https://si.com/mlb-draft/carson-kerce-signs",
                  "quote": "Kerce has signed with the Diamondbacks."}
    tier, payload = news_scan.decide(extraction, {}, TODAY)
    assert tier == "reported"
    assert payload == {"bonus": 1900000,
                        "source": "https://si.com/mlb-draft/carson-kerce-signs"}


def test_decide_www_prefix_passes_whitelist():
    """Real feeds publish www-prefixed URLs (the committed gnews fixture's SI
    source is literally https://www.si.com) — the whitelist check must
    normalize the leading www. or every RSS report lands as unverified."""
    extraction = {"event": "signed", "amount": 1900000,
                  "source_url": "https://www.si.com",
                  "quote": "Kerce has signed with the Diamondbacks."}
    tier, payload = news_scan.decide(extraction, {}, TODAY)
    assert tier == "reported"
    assert payload == {"bonus": 1900000, "source": "https://www.si.com"}


def test_decide_whitelist_subdomain_passes():
    extraction = {"event": "signed", "amount": 1900000,
                  "source_url": "https://news.si.com/mlb/kerce-signs",
                  "quote": "Kerce has signed with the Diamondbacks."}
    tier, _ = news_scan.decide(extraction, {}, TODAY)
    assert tier == "reported"


def test_decide_lookalike_domain_is_not_whitelisted():
    """`notsi.com` merely ends with the characters "si.com" — the suffix rule
    must match on `.si.com` (dot included) so lookalikes stay unverified."""
    extraction = {"event": "signed", "amount": 1900000,
                  "source_url": "https://notsi.com/mlb/kerce-signs",
                  "quote": "Kerce has signed with the Diamondbacks."}
    tier, payload = news_scan.decide(extraction, {}, TODAY)
    assert tier == "unverified"
    assert payload["detected"] == TODAY


def test_decide_mlb_com_subdomain_passes_whitelist():
    """`mlb.com` itself is in WHITELIST, but real MLB pages hang off subdomains
    (e.g. www.mlb.com) which are not literally in the set -- the whitelist
    suffix rule must catch anything ending in `.mlb.com`."""
    extraction = {"event": "signed", "amount": 500000,
                  "source_url": "https://www.mlb.com/news/2026-draft-signing-tracker",
                  "quote": "Kerce has signed with the Diamondbacks."}
    tier, payload = news_scan.decide(extraction, {}, TODAY)
    assert tier == "reported"
    assert payload["source"] == "https://www.mlb.com/news/2026-draft-signing-tracker"


def test_decide_non_whitelisted_signed_is_unverified_with_detected_today():
    extraction = {"event": "signed", "amount": 9000000,
                  "source_url": "https://gtswarm.com/threads/2026-mlb-draft.31400/post-1",
                  "quote": "Lackey has agreed to terms."}
    tier, payload = news_scan.decide(extraction, {}, TODAY)
    assert tier == "unverified"
    assert payload == {"bonus": 9000000,
                        "source": "https://gtswarm.com/threads/2026-mlb-draft.31400/post-1",
                        "detected": TODAY}


def test_decide_same_source_url_is_idempotent():
    """A second run that would produce the identical unverified block (same
    source URL) must be a no-op, not a duplicate write."""
    entry = {"unverified": {"bonus": 9000000,
                            "source": "https://gtswarm.com/threads/2026-mlb-draft.31400/post-1",
                            "detected": "2026-07-20"}}
    extraction = {"event": "signed", "amount": 9000000,
                  "source_url": "https://gtswarm.com/threads/2026-mlb-draft.31400/post-1",
                  "quote": "Lackey has agreed to terms."}
    assert news_scan.decide(extraction, entry, TODAY) == (None, None)


def test_decide_never_overwrites_existing_reported():
    entry = {"reported": {"bonus": 1800000, "source": "https://old.example/article"}}
    extraction = {"event": "signed", "amount": 1900000,
                  "source_url": "https://si.com/mlb-draft/carson-kerce-signs",
                  "quote": "Kerce has signed."}
    assert news_scan.decide(extraction, entry, TODAY) == (None, None)


def test_decide_never_touches_entry_with_official_bonus():
    """`entry` is a draft.yaml block, which has no field of its own for the
    official MLB picks-feed bonus -- see news_scan._official_known's docstring
    for the documented contract (caller merges `official_bonus` into entry)."""
    entry = {"official_bonus": 500000}
    extraction = {"event": "signed", "amount": 9000000,
                  "source_url": "https://fan.example/thread",
                  "quote": "Signed for $9M, per a fan board post."}
    assert news_scan.decide(extraction, entry, TODAY) == (None, None)


def test_decide_signed_without_amount_is_flagged():
    extraction = {"event": "signed", "amount": None,
                  "source_url": "https://fan.example/thread",
                  "quote": "Kerce is signing soon, no figure yet."}
    tier, payload = news_scan.decide(extraction, {}, TODAY)
    assert tier == "flag"
    assert payload == {"event": "signed", "source_url": "https://fan.example/thread",
                        "quote": "Kerce is signing soon, no figure yet.", "seen": TODAY}


def test_decide_expected_is_flagged():
    extraction = {"event": "expected", "amount": None,
                  "source_url": "https://fan.example/thread",
                  "quote": "Kerce is expected to sign this week."}
    tier, payload = news_scan.decide(extraction, {}, TODAY)
    assert tier == "flag"
    assert payload["event"] == "expected"


def test_decide_rumor_is_flagged():
    extraction = {"event": "rumor", "amount": None,
                  "source_url": "https://fan.example/thread",
                  "quote": "Word is Kerce is close to a deal."}
    tier, payload = news_scan.decide(extraction, {}, TODAY)
    assert tier == "flag"
    assert payload["event"] == "rumor"


def test_decide_none_event_does_nothing():
    assert news_scan.decide({"event": "none"}, {}, TODAY) == (None, None)


# ---------------------------------------------------------------------------
# fetch_snippets() -- fixture-driven, fake session_get injected
# ---------------------------------------------------------------------------

def _fake_session_get(url):
    if url.startswith("https://news.google.com/rss"):
        return (FIX / "gnews_kerce.xml").read_bytes()
    if "gtswarm.com" in url:
        return (FIX / "gtswarm_page.html").read_text()
    raise RuntimeError(f"no fixture wired for {url}")


def test_fetch_snippets_finds_rss_item_with_source_url():
    snippets = news_scan.fetch_snippets("Carson Kerce", _fake_session_get)
    rss_hits = [s for s in snippets if "kerce" in s["text"].lower()
                and "gtswarm.com" not in s["url"]]
    assert rss_hits, snippets
    assert all(s["url"] for s in rss_hits)


def test_fetch_snippets_captures_gtswarm_mention():
    snippets = news_scan.fetch_snippets("Carson Kerce", _fake_session_get)
    gts_hits = [s for s in snippets if "gtswarm.com" in s["url"]]
    assert gts_hits, snippets
    assert all("kerce" in s["text"].lower() for s in gts_hits)


def test_fetch_snippets_deduped_by_url():
    snippets = news_scan.fetch_snippets("Carson Kerce", _fake_session_get)
    urls = [s["url"] for s in snippets]
    assert len(urls) == len(set(urls))


def test_fetch_snippets_unknown_player_yields_nothing():
    assert news_scan.fetch_snippets("Zzyzx Wibblefarb", _fake_session_get) == []


def test_fetch_snippets_isolates_per_source_failure():
    """The MLB tracker source has no fixture and always raises in this test;
    fetch_snippets must swallow that and still return the other sources'
    snippets rather than blowing up the whole call."""
    snippets = news_scan.fetch_snippets("Carson Kerce", _fake_session_get)
    assert isinstance(snippets, list) and snippets


# ---------------------------------------------------------------------------
# _extract() -- the Anthropic seam
# ---------------------------------------------------------------------------

class _FakeBlock:
    def __init__(self, text):
        self.text = text


class _FakeMessages:
    def __init__(self, text):
        self._text = text

    def create(self, **kwargs):
        return type("FakeResp", (), {"content": [_FakeBlock(self._text)]})()


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


def test_extract_malformed_json_returns_none_event(monkeypatch):
    monkeypatch.setattr(news_scan, "_client", lambda: _FakeClient("not valid json {{"))
    result = news_scan._extract([{"text": "Kerce signed.", "url": "https://si.com/x"}],
                                 "Carson Kerce")
    assert result == {"event": "none"}


def test_extract_missing_event_key_returns_none_event(monkeypatch):
    monkeypatch.setattr(news_scan, "_client",
                         lambda: _FakeClient('{"amount": 100, "source_url": "https://x"}'))
    result = news_scan._extract([{"text": "Kerce signed.", "url": "https://si.com/x"}],
                                 "Carson Kerce")
    assert result == {"event": "none"}


def test_extract_valid_json_passes_through(monkeypatch):
    payload = ('{"event": "signed", "amount": 1900000, '
               '"source_url": "https://si.com/x", "quote": "Kerce signed."}')
    monkeypatch.setattr(news_scan, "_client", lambda: _FakeClient(payload))
    result = news_scan._extract([{"text": "Kerce signed.", "url": "https://si.com/x"}],
                                 "Carson Kerce")
    assert result == {"event": "signed", "amount": 1900000,
                       "source_url": "https://si.com/x", "quote": "Kerce signed."}


def test_extract_client_raising_returns_none_event(monkeypatch):
    def _boom():
        raise RuntimeError("no api key configured")
    monkeypatch.setattr(news_scan, "_client", _boom)
    result = news_scan._extract([{"text": "Kerce signed.", "url": "https://si.com/x"}],
                                 "Carson Kerce")
    assert result == {"event": "none"}


def test_extract_quote_about_different_player_downgraded_to_none(monkeypatch):
    """Spec guard: exact player-name match required in the quote. A model
    answer whose quote never mentions the player's last name (it latched onto
    a teammate in the same snippet) must be downgraded to none, enforced in
    _extract post-validation so decide() stays a pure tier policy."""
    payload = ('{"event": "signed", "amount": 500000, '
               '"source_url": "https://si.com/x", '
               '"quote": "Tate McKee has agreed to terms with the Braves."}')
    monkeypatch.setattr(news_scan, "_client", lambda: _FakeClient(payload))
    result = news_scan._extract(
        [{"text": "McKee signed; Kerce still unsigned.", "url": "https://si.com/x"}],
        "Carson Kerce")
    assert result == {"event": "none"}


# ---------------------------------------------------------------------------
# default_session_get() -- the production session_get for draft_watch
# ---------------------------------------------------------------------------

def test_default_session_get_browser_ua_timeout_and_status_check(monkeypatch):
    captured = {}

    class _FakeResp:
        content = b"<rss>payload</rss>"

        def raise_for_status(self):
            captured["status_checked"] = True

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(news_scan.requests, "get", fake_get)
    out = news_scan.default_session_get("https://news.google.com/rss/search?q=x")
    assert out == b"<rss>payload</rss>"
    assert captured["url"] == "https://news.google.com/rss/search?q=x"
    assert captured["headers"]["User-Agent"].startswith("Mozilla/5.0")
    assert captured["timeout"] == 30
    assert captured.get("status_checked")
