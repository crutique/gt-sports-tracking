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
        "Vahn Lackey",
        {"event": "signed", "amount": 9000000,
         "source_url": "https://gtswarm.com/threads/2026-mlb-draft.31400/post-1",
         "quote": "Lackey has agreed to terms."}))

    rc = draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                          out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    assert rc == 0

    new_lines = draft_path.read_text().splitlines()
    lackey_line = next(l for l in new_lines if l.startswith("- {name: Vahn Lackey"))
    assert lackey_line.startswith("- {name:")
    assert "unverified: {bonus: 9000000" in lackey_line
    assert '"https://gtswarm.com/threads/2026-mlb-draft.31400/post-1"' in lackey_line
    assert 'detected: "2026-07-21"' in lackey_line

    # every OTHER line -- comments included -- must survive byte-for-byte
    original_lines = REAL_DRAFT_YAML.read_text().splitlines()
    for orig, new in zip(original_lines, new_lines):
        if orig.startswith("- {name: Vahn Lackey"):
            continue
        assert orig == new
    assert original_lines[0].startswith("#")   # sanity: this really is a comment line
    assert original_lines[0] == new_lines[0]

    draft_json = json.loads((out_dir / "draft.json").read_text())
    lackey = next(p for p in draft_json["players"] if p["name"] == "Vahn Lackey")
    assert lackey["bonus"] == 9000000
    assert lackey["bonusSource"] == "unverified"
    assert lackey["status"] == "unsigned"          # unverified never implies signed


def test_unverified_rerun_is_idempotent_no_duplicate_key(tmp_path, monkeypatch, api):
    """A second run producing the identical source URL must not append a
    second `unverified:` key (which would make the YAML line invalid)."""
    draft_path = _copy_draft_yaml(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    extraction = {"event": "signed", "amount": 9000000,
                  "source_url": "https://gtswarm.com/threads/2026-mlb-draft.31400/post-1",
                  "quote": "Lackey has agreed to terms."}
    monkeypatch.setattr(news_scan, "_extract", _extract_only_for("Vahn Lackey", extraction))

    draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                     out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    rc2 = draft_watch.run(today="2026-07-22", draft_path=str(draft_path),
                           out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    assert rc2 == 0

    lines = draft_path.read_text().splitlines()
    lackey_line = next(l for l in lines if l.startswith("- {name: Vahn Lackey"))
    assert lackey_line.count("unverified:") == 1
    assert 'detected: "2026-07-21"' in lackey_line   # not overwritten with the 2nd run's date


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


# ---------------------------------------------------------------------------
# (d) missing ANTHROPIC_API_KEY -- scan skipped, official refresh still runs
# ---------------------------------------------------------------------------

def test_missing_api_key_skips_scan_but_refreshes_official(tmp_path, monkeypatch, api, capsys):
    draft_path = _copy_draft_yaml(tmp_path)
    out_dir = tmp_path / "out"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def _must_not_be_called(*a, **k):
        pytest.fail("news_scan._extract should not be called when the key is absent")
    monkeypatch.setattr(news_scan, "_extract", _must_not_be_called)

    rc = draft_watch.run(today="2026-07-21", draft_path=str(draft_path),
                          out_dir=str(out_dir), flags_path=str(tmp_path / "flags.json"))
    assert rc == 0

    draft_json = json.loads((out_dir / "draft.json").read_text())
    assert draft_json["players"]                   # official refresh really did run

    captured = capsys.readouterr()
    assert "scan=skipped" in captured.out
