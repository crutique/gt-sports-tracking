"""Orchestrator: gate on the draft-signing season window, refresh the official
draft signal + regenerate site/src/data/draft.json, then run the news scanner
for every open player and apply its verdicts. CLI entry:
`python -m pipeline.draft_watch` (see .github/workflows/draft-watch.yml).

Per docs/superpowers/specs/2026-07-20-draft-watch-design.md ("Orchestrator"):
  1. Date gate: exit 0 quietly outside WINDOW.
  2. Refresh official signals via draft_registry/draft_status, write draft.json.
  3. If ANTHROPIC_API_KEY is set, scan each open player and apply news_scan's
     verdict: reported/unverified edits pipeline/draft.yaml, flag appends to
     the flags file. Skipped (with a visible summary note) if the key is absent.
  4. Print a one-line summary; return 0 on success (per-source/per-player
     failures are isolated and logged, never fatal), nonzero only if the
     official refresh itself fails outright.
"""
import datetime
import json
import os
import sys
from pathlib import Path

import yaml

from pipeline import draft_registry, draft_status, news_scan

WINDOW = ("2026-06-10", "2026-08-05")

DEFAULT_DRAFT_PATH = "pipeline/draft.yaml"
DEFAULT_OUT_DIR = "site/src/data"
DEFAULT_FLAGS_PATH = "data/draft-watch-flags.json"
DEFAULT_PLAYERS_PATH = "pipeline/players.yaml"

_TIER_KEY_ORDER = {
    "reported": ("bonus", "source"),
    "unverified": ("bonus", "source", "detected"),
}


# ---------------------------------------------------------------------------
# HTTP seam -- news_scan.default_session_get is the real fetch (browser UA,
# 30s timeout, raise_for_status); this module-level name is what tests
# monkeypatch (mirrors draft_status._get's seam convention) so no test here
# ever touches the network.
# ---------------------------------------------------------------------------

_session_get = news_scan.default_session_get


# ---------------------------------------------------------------------------
# draft.yaml line-targeted editing -- byte-preserving except the one entry line
# ---------------------------------------------------------------------------

def _find_entry_close_index(line, start):
    """Index of the '}' that matches the '{' at `start`, brace-depth aware and
    quote-aware (so a source URL or note text can never desync the count)."""
    depth = 0
    in_str = None
    for i in range(start, len(line)):
        ch = line[i]
        if in_str:
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unbalanced braces in draft.yaml entry line: {line!r}")


def _split_flow_pairs(inner):
    """Split a flow-mapping's inner `key: value, key: value` content on its
    TOP-LEVEL commas only -- commas inside a nested `{...}` value (e.g. an
    existing `reported: {bonus: 1, source: "..."}`) must not split it apart."""
    pairs, buf, depth, in_str = [], [], 0, None
    for ch in inner:
        if in_str:
            buf.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            pairs.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        pairs.append("".join(buf))
    return pairs


def _render_flow_map(payload, key_order):
    parts = []
    for k in key_order:
        v = payload[k]
        parts.append(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}")
    return "{" + ", ".join(parts) + "}"


def _set_flow_key(line, key, value_yaml):
    """Return `line` with top-level key `key` set to `value_yaml` inside its
    leading `{...}` flow map -- replacing it if already present, appending it
    otherwise. Everything outside the map (leading text, trailing comment,
    line ending) is passed through untouched."""
    open_idx = line.index("{")
    close_idx = _find_entry_close_index(line, open_idx)
    pairs = _split_flow_pairs(line[open_idx + 1:close_idx])
    new_pair = f" {key}: {value_yaml}"
    for i, p in enumerate(pairs):
        if p.split(":", 1)[0].strip() == key:
            pairs[i] = new_pair
            break
    else:
        pairs.append(new_pair)
    return line[:open_idx + 1] + ",".join(pairs) + line[close_idx:]


def _rewrite_draft_yaml(path, player_name, key, value_yaml):
    """Line-targeted edit: find the one line whose parsed entry name matches
    `player_name` and rewrite only that line, preserving every other byte of
    the file (including comments) exactly. Returns True if a line was edited."""
    lines = Path(path).read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not (stripped.startswith("- {") or stripped.startswith("-{")):
            continue
        try:
            parsed = yaml.safe_load(stripped)
        except yaml.YAMLError:
            continue
        if not (isinstance(parsed, list) and parsed and isinstance(parsed[0], dict)
                and parsed[0].get("name") == player_name):
            continue
        lines[i] = _set_flow_key(line, key, value_yaml)
        Path(path).write_text("".join(lines))
        return True
    return False


def _apply_tier(draft_path, player_name, tier, payload):
    value_yaml = _render_flow_map(payload, _TIER_KEY_ORDER[tier])
    return _rewrite_draft_yaml(draft_path, player_name, tier, value_yaml)


# ---------------------------------------------------------------------------
# flags file -- deduped by source_url
# ---------------------------------------------------------------------------

def _load_flags(flags_path):
    p = Path(flags_path)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _append_flag(flags_path, flag):
    """Append `flag` unless one with the same source_url is already present.
    Returns True if it was appended."""
    flags = _load_flags(flags_path)
    if any(f.get("source_url") == flag.get("source_url") for f in flags):
        return False
    flags.append(flag)
    p = Path(flags_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(flags, indent=1))
    return True


# ---------------------------------------------------------------------------
# orchestrator
# ---------------------------------------------------------------------------

def _player_slugs(players_path):
    with open(players_path) as f:
        players = yaml.safe_load(f) or []
    return {p["slug"] for p in players if p.get("slug")}


def _is_open(player):
    """Open per spec ("News scanner"): status not signed, or signed without an
    official bonus -- i.e. NOT (signed AND official). Equivalently: status !=
    "signed" OR bonusSource != "official". A curated `reported:` figure (still
    open by this rule) is harmless to re-scan -- decide() already refuses to
    touch an entry that already has a `reported` block."""
    return player["status"] != "signed" or player.get("bonusSource") != "official"


def _write_draft_json(entries, today, out_dir):
    draft_json = draft_status.build_draft(entries, today)
    os.makedirs(out_dir, exist_ok=True)
    Path(out_dir, "draft.json").write_text(json.dumps(draft_json, indent=1))
    return draft_json


def run(today=None, draft_path=DEFAULT_DRAFT_PATH, out_dir=DEFAULT_OUT_DIR,
        flags_path=DEFAULT_FLAGS_PATH, players_path=DEFAULT_PLAYERS_PATH):
    today = today or datetime.date.today().isoformat()

    if not (WINDOW[0] <= today <= WINDOW[1]):
        print(f"[watch] outside window {WINDOW} (today={today}), skipping")
        return 0

    try:
        slugs = _player_slugs(players_path)
        entries = draft_registry.load_draft(draft_path, slugs)
        draft_json = _write_draft_json(entries, today, out_dir)
    except Exception as exc:  # noqa: BLE001 -- official refresh failing IS fatal
        print(f"[watch] FAILED official refresh: {exc}", file=sys.stderr)
        return 1

    official_count = sum(1 for p in draft_json["players"] if p["bonusSource"] == "official")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"[watch] official={official_count} reported=0 unverified=0 flags=0 scan=skipped")
        return 0

    players_by_name = {p["name"]: p for p in draft_json["players"]}
    reported_count = unverified_count = flags_count = 0
    yaml_changed = False

    for e in entries:
        if e.get("udfa"):
            continue
        player = players_by_name.get(e["name"])
        if player is None or not _is_open(player):
            continue
        try:
            official_bonus = player["bonus"] if player.get("bonusSource") == "official" else None
            merged_entry = dict(e, official_bonus=official_bonus)
            snippets = news_scan.fetch_snippets(e["name"], _session_get)
            extraction = news_scan._extract(snippets, e["name"])
            tier, payload = news_scan.decide(extraction, merged_entry, today)
            if tier in ("reported", "unverified"):
                if _apply_tier(draft_path, e["name"], tier, payload):
                    yaml_changed = True
                    if tier == "reported":
                        reported_count += 1
                    else:
                        unverified_count += 1
            elif tier == "flag":
                flag = {"player": e["name"], **payload}
                if _append_flag(flags_path, flag):
                    flags_count += 1
        except Exception as exc:  # noqa: BLE001 -- one player's scan must never sink the run
            print(f"[news_scan] warning: scan failed for {e['name']!r}: {exc}")

    if yaml_changed:
        entries = draft_registry.load_draft(draft_path, slugs)
        _write_draft_json(entries, today, out_dir)

    print(f"[watch] official={official_count} reported={reported_count} "
          f"unverified={unverified_count} flags={flags_count} skipped-sources=[]")
    return 0


def main():
    sys.exit(run())


if __name__ == "__main__":
    main()
