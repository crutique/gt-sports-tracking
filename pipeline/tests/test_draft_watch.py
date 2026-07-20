import json
from pathlib import Path

import pytest

from pipeline import draft_status, draft_watch, news_scan

FIX_DRAFT = Path("pipeline/fixtures/draft")
REAL_DRAFT_YAML = Path("pipeline/draft.yaml")


def _fake_get(url):
    """Mirrors test_draft_status.py's `api` fixture -- routes draft_status._get
    to the same offline fixtures so build_draft never touches the network."""
    if "/draft/2026" in url:
        return json.loads((FIX_DRAFT / "draft_2026.json").read_text())
    if "playerId=702701" in url:
        return json.loads((FIX_DRAFT / "transactions_702701.json").read_text())
    if "/transactions" in url:
        return {"transactions": []}
    raise AssertionError(f"unexpected url {url}")


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(draft_status, "_get", _fake_get)


@pytest.fixture(autouse=True)
def _no_scan_network(monkeypatch):
    """draft_watch's own HTTP seam -- fetch_snippets' three sources each raise
    and get swallowed by fetch_snippets' per-source isolation, so this always
    yields an empty snippet list. Every test in this file also monkeypatches
    news_scan._extract directly, so the (empty) snippets content never
    actually matters -- this fixture just guarantees no test hits the network."""
    def _boom(url):
        raise RuntimeError("network disabled in tests")
    monkeypatch.setattr(draft_watch, "_session_get", _boom)


def _copy_draft_yaml(tmp_path):
    dst = tmp_path / "draft.yaml"
    dst.write_text(REAL_DRAFT_YAML.read_text())
    return dst


def _extract_only_for(target_name, extraction):
    def _fake(snippets, player_name):
        if player_name == target_name:
            return extraction
        return {"event": "none"}
    return _fake


# ---------------------------------------------------------------------------
# (a) window gate
# ---------------------------------------------------------------------------

def test_run_outside_window_returns_zero_no_writes(tmp_path, monkeypatch):
    draft_path = _copy_draft_yaml(tmp_path)
    original = draft_path.read_text()
    out_dir = tmp_path / "out"
    flags_path = tmp_path / "flags.json"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unused-should-not-matter")

    rc = draft_watch.run(today="2026-08-20", draft_path=str(draft_path),
                          out_dir=str(out_dir), flags_path=str(flags_path))

    assert rc == 0
    assert draft_path.read_text() == original     # untouched
    assert not out_dir.exists()                    # no draft.json write attempted
    assert not flags_path.exists()


def test_run_before_window_returns_zero_no_writes(tmp_path, monkeypatch):
    draft_path = _copy_draft_yaml(tmp_path)
    original = draft_path.read_text()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unused")

    rc = draft_watch.run(today="2026-01-01", draft_path=str(draft_path),
                          out_dir=str(tmp_path / "out"),
                          flags_path=str(tmp_path / "flags.json"))

    assert rc == 0
    assert draft_path.read_text() == original


# ---------------------------------------------------------------------------
# (b) unverified result edits draft.yaml (byte-preserving) + regenerates draft.json
# ---------------------------------------------------------------------------

def test_unverified_result_edits_yaml_preserving_flow_style_and_regenerates_json(
        tmp_path, monkeypatch, api):
    draft_path = _copy_draft_yaml(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(news_scan, "_extract", _extract_only_for(
        "Tate McKee",
        {"event": "signed", "amount": 9000000,
         "source_url": "https://gtswarm.com/threads/2026-mlb-draft.31400/post-1",
         "quote": "McKee has agreed to terms."}))

    rc = draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                          out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    assert rc == 0

    new_lines = draft_path.read_text().splitlines()
    mckee_line = next(l for l in new_lines if l.startswith("- {name: Tate McKee"))
    assert mckee_line.startswith("- {name:")
    assert "unverified: {bonus: 9000000" in mckee_line
    assert '"https://gtswarm.com/threads/2026-mlb-draft.31400/post-1"' in mckee_line
    assert 'detected: "2026-07-21"' in mckee_line

    # every OTHER line -- comments included -- must survive byte-for-byte
    original_lines = REAL_DRAFT_YAML.read_text().splitlines()
    assert len(original_lines) == len(new_lines)
    for orig, new in zip(original_lines, new_lines):
        if orig.startswith("- {name: Tate McKee"):
            continue
        assert orig == new
    assert original_lines[0].startswith("#")   # sanity: this really is a comment line
    assert original_lines[0] == new_lines[0]

    draft_json = json.loads((out_dir / "draft.json").read_text())
    mckee = next(p for p in draft_json["players"] if p["name"] == "Tate McKee")
    assert mckee["bonus"] == 9000000
    assert mckee["bonusSource"] == "unverified"
    assert mckee["status"] == "unsigned"          # unverified never implies signed


def test_unverified_rerun_is_idempotent_no_duplicate_key(tmp_path, monkeypatch, api):
    """A second run producing the identical source URL must not append a
    second `unverified:` key (which would make the YAML line invalid)."""
    draft_path = _copy_draft_yaml(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    extraction = {"event": "signed", "amount": 9000000,
                  "source_url": "https://gtswarm.com/threads/2026-mlb-draft.31400/post-1",
                  "quote": "McKee has agreed to terms."}
    monkeypatch.setattr(news_scan, "_extract", _extract_only_for("Tate McKee", extraction))

    draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                     out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    rc2 = draft_watch.run(today="2026-07-22", draft_path=str(draft_path),
                           out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    assert rc2 == 0

    lines = draft_path.read_text().splitlines()
    mckee_line = next(l for l in lines if l.startswith("- {name: Tate McKee"))
    assert mckee_line.count("unverified:") == 1
    assert 'detected: "2026-07-21"' in mckee_line   # not overwritten with the 2nd run's date


# ---------------------------------------------------------------------------
# (c) flag result appends deduped entries to data/draft-watch-flags.json
# ---------------------------------------------------------------------------

def test_flag_result_appends_to_flags_file_deduped_by_source_url(tmp_path, monkeypatch, api):
    draft_path = _copy_draft_yaml(tmp_path)
    out_dir = tmp_path / "out"
    flags_path = tmp_path / "flags.json"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(news_scan, "_extract", _extract_only_for(
        "Drew Burress",
        {"event": "expected", "amount": None,
         "source_url": "https://fan.example/thread",
         "quote": "Burress is expected to sign this week."}))

    rc = draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                          out_dir=str(out_dir), flags_path=str(flags_path))
    assert rc == 0

    flags = json.loads(flags_path.read_text())
    assert len(flags) == 1
    assert flags[0]["player"] == "Drew Burress"
    assert flags[0]["event"] == "expected"
    assert flags[0]["source_url"] == "https://fan.example/thread"

    # re-run with the identical extraction -- must not duplicate
    rc2 = draft_watch.run(today="2026-07-22", draft_path=str(draft_path),
                           out_dir=str(out_dir), flags_path=str(flags_path))
    assert rc2 == 0
    flags2 = json.loads(flags_path.read_text())
    assert len(flags2) == 1


def test_flag_dedupe_is_per_player_and_source_url(tmp_path, monkeypatch, api):
    """The MLB tracker is ONE constant URL that names many players; a dedupe
    keyed on source_url alone would suppress every player after the first.
    The key must be (player, source_url): different players from the same URL
    both persist, while the same player + same URL still dedupes on re-run."""
    draft_path = _copy_draft_yaml(tmp_path)
    out_dir = tmp_path / "out"
    flags_path = tmp_path / "flags.json"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    tracker_url = "https://www.mlb.com/news/2026-mlb-draft-signing-tracker"

    def _fake_extract(snippets, player_name):
        if player_name in ("Drew Burress", "Tate McKee"):
            return {"event": "expected", "amount": None, "source_url": tracker_url,
                    "quote": f"{player_name} is expected to sign this week."}
        return {"event": "none"}
    monkeypatch.setattr(news_scan, "_extract", _fake_extract)

    rc = draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                          out_dir=str(out_dir), flags_path=str(flags_path))
    assert rc == 0
    flags = json.loads(flags_path.read_text())
    assert {(f["player"], f["source_url"]) for f in flags} == {
        ("Drew Burress", tracker_url), ("Tate McKee", tracker_url)}
    assert len(flags) == 2

    # same players + same URL on a re-run -- still no duplicates
    rc2 = draft_watch.run(today="2026-07-22", draft_path=str(draft_path),
                           out_dir=str(out_dir), flags_path=str(flags_path))
    assert rc2 == 0
    assert len(json.loads(flags_path.read_text())) == 2


# ---------------------------------------------------------------------------
# (d) missing credentials -- scan skipped, official refresh still runs;
#     scan runs when EITHER ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN is set
# ---------------------------------------------------------------------------

def test_missing_both_credentials_skips_scan_but_refreshes_official(
        tmp_path, monkeypatch, api, capsys):
    draft_path = _copy_draft_yaml(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

    def _must_not_be_called(*a, **k):
        pytest.fail("news_scan._extract should not be called when neither "
                    "credential is present")
    monkeypatch.setattr(news_scan, "_extract", _must_not_be_called)

    rc = draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                          out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    assert rc == 0

    draft_json = json.loads((out_dir / "draft.json").read_text())
    assert draft_json["players"]                   # official refresh really did run

    captured = capsys.readouterr()
    assert "scan=skipped" in captured.out


def test_missing_both_credentials_as_empty_strings_skips_scan(
        tmp_path, monkeypatch, api, capsys):
    """Empty-string env vars (e.g. an unset GitHub Actions secret, which
    resolves to '') must be treated as absent -- truthiness, not `in`."""
    draft_path = _copy_draft_yaml(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "")

    def _must_not_be_called(*a, **k):
        pytest.fail("news_scan._extract should not be called for empty-string credentials")
    monkeypatch.setattr(news_scan, "_extract", _must_not_be_called)

    rc = draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                          out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    assert rc == 0

    captured = capsys.readouterr()
    assert "scan=skipped" in captured.out


def test_run_with_only_oauth_token_runs_scan(tmp_path, monkeypatch, api):
    """The scan gate accepts EITHER credential -- with only CLAUDE_CODE_OAUTH_TOKEN
    set (no ANTHROPIC_API_KEY), the scan must still run and apply verdicts."""
    draft_path = _copy_draft_yaml(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "test-oauth-token")
    monkeypatch.setattr(news_scan, "_extract", _extract_only_for(
        "Tate McKee",
        {"event": "signed", "amount": 9000000,
         "source_url": "https://gtswarm.com/threads/2026-mlb-draft.31400/post-1",
         "quote": "McKee has agreed to terms."}))

    rc = draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                          out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    assert rc == 0

    new_lines = draft_path.read_text().splitlines()
    mckee_line = next(l for l in new_lines if l.startswith("- {name: Tate McKee"))
    assert "unverified: {bonus: 9000000" in mckee_line


def test_run_stamps_meta_heartbeat(tmp_path, monkeypatch):
    import json as _json
    draft_path = tmp_path / "draft.yaml"
    draft_path.write_text("- {name: A, person_id: 1, gt_role: departing}\n")
    out = tmp_path / "out"
    monkeypatch.setattr(draft_status, "build_draft",
                        lambda entries, today, deadline=draft_status.DEADLINE:
                        {"asOf": today, "players": [], "udfa": []})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    rc = draft_watch.run(today="2026-07-21", draft_path=str(draft_path), out_dir=str(out),
                         flags_path=str(tmp_path / "f.json"))
    assert rc == 0
    meta = _json.loads((out / "meta.json").read_text())
    assert meta["source"] == "draft-watch" and meta["generatedAt"]
