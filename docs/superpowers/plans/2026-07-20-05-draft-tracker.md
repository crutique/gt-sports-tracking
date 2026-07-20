# MLB Draft Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A nightly-updated `/draft` page tracking GT's 2026 MLB draft class — signed/unsigned, bonus (official or sourced-reported), and return-to-GT status.

**Architecture:** A curated `pipeline/draft.yaml` (class list + news-driven fields) merges nightly with two MLB StatsAPI feeds (draft picks for bonus/slot/headshot, transactions for same-day signed flags) in a new `pipeline/draft_status.py`, wired into `build_data` with the same per-unit failure isolation as leagues. Output is `site/src/data/draft.json`, rendered by a new Astro `/draft` page.

**Tech Stack:** Python 3.12 (`.venv/bin/python` — bare `python3` on this machine is 3.7), requests, pytest fixtures (offline tests), Astro 5 + vitest.

**Spec:** `docs/superpowers/specs/2026-07-20-draft-tracker-design.md` — read it first.

---

### Task 0: Research verification (no code)

Resolve the spec's three research prerequisites. Use WebSearch/WebFetch/curl. Produce a short findings block that Task 1 seeds into draft.yaml.

- [ ] **Step 1: Other drafted GT signees.** Fetch `https://statsapi.mlb.com/api/v1/draft/2026` and extract every HS pick's name (school.name not containing "Georgia Tech"). Cross-check against GT's 2026 signing class (search "Georgia Tech baseball signing class 2026", ramblinwreck.com announcements, Perfect Game commitments list for GT). Known GT freshman signees to check by name: Deion Cole, Jack Richerson, Ezekiel Lara, Kolby Martin, Ryan Engle, Luke Nitkowski, Reid Gainous, Michael Nottleman, Brett Slymen, Isaiah Galason (already known: R17 #496). Output: list of any additional drafted signees with person_id, round, pick, team — or "none".
- [ ] **Step 2: Mason Patel UDFA.** Verify the reported UDFA signing with the Athletics: exact date and a source URL (search "Mason Patel" Athletics undrafted, Georgia Tech; check GTSwarm draft thread, On3, team release). If it cannot be confirmed by any citable source, output "unverified" — Task 1 then omits his entry and leaves a dated comment instead.
- [ ] **Step 3: Brosius bonus.** StatsAPI shows `signingBonus: '500'` (string) for pick 262. Verify the real figure via reporting (search "Parker Brosius" Braves signing bonus; Spotrac round 9 via browser if needed, Baseball America, 13WMAZ/AJC). Output: confirmed dollar amount + source URL, or "unconfirmed" (Task 1 then adds a `reported:` only if a source exists; the pipeline will otherwise display the API value once it is plausible — see Task 2 `_bonus` note).

No commit — findings feed Task 1.

### Task 1: Curated registry — draft.yaml + loader

**Files:**
- Create: `pipeline/draft.yaml`
- Create: `pipeline/draft_registry.py`
- Test: `pipeline/tests/test_draft_registry.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from pipeline import draft_registry
from pipeline.registry import RegistryError

SLUGS = {"isaiah-galason"}


def _write(tmp_path, text):
    p = tmp_path / "draft.yaml"
    p.write_text(text)
    return str(p)


def test_load_seed_file():
    entries = draft_registry.load_draft("pipeline/draft.yaml", SLUGS)
    names = [e["name"] for e in entries]
    assert "Vahn Lackey" in names and "Isaiah Galason" in names
    galason = next(e for e in entries if e["name"] == "Isaiah Galason")
    assert galason["gt_role"] == "signee" and galason["slug"] == "isaiah-galason"


def test_duplicate_name_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: departing}\n"
                            "- {name: A, person_id: 2, gt_role: departing}\n")
    with pytest.raises(RegistryError, match="duplicate"):
        draft_registry.load_draft(path, set())


def test_bad_gt_role_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: alumni}\n")
    with pytest.raises(RegistryError, match="gt_role"):
        draft_registry.load_draft(path, set())


def test_non_udfa_needs_numeric_person_id(tmp_path):
    path = _write(tmp_path, "- {name: A, gt_role: departing}\n")
    with pytest.raises(RegistryError, match="person_id"):
        draft_registry.load_draft(path, set())


def test_udfa_needs_team(tmp_path):
    path = _write(tmp_path, "- {name: A, gt_role: departing, udfa: {date: '2026-07-15'}}\n")
    with pytest.raises(RegistryError, match="udfa"):
        draft_registry.load_draft(path, set())


def test_reported_needs_bonus_and_source(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: departing, reported: {bonus: 100}}\n")
    with pytest.raises(RegistryError, match="reported"):
        draft_registry.load_draft(path, set())


def test_unknown_slug_rejected(tmp_path):
    path = _write(tmp_path, "- {name: A, person_id: 1, gt_role: signee, slug: nobody}\n")
    with pytest.raises(RegistryError, match="slug"):
        draft_registry.load_draft(path, {"someone-else"})
```

- [ ] **Step 2: Run** `.venv/bin/pytest pipeline/tests/test_draft_registry.py -q` — expect FAIL (module/file missing).

- [ ] **Step 3: Create `pipeline/draft.yaml`** — seed with the verified class. Base content (adjust with Task 0 findings: add any extra drafted signees; include Patel only if verified, with his real date/source; add Brosius `reported:` only if Task 0 produced a source):

```yaml
# GT 2026 MLB Draft class. Curated fields per docs/superpowers/specs/2026-07-20-draft-tracker-design.md:
#   reported: {bonus, source}  — reporter-broken figure (labeled until official lands)
#   returning: true + note     — news-driven declarations; note also covers nuance
- {name: Vahn Lackey, person_id: 822518, gt_role: departing}
- {name: Drew Burress, person_id: 806039, gt_role: departing}
- {name: Jarren Advincula, person_id: 814181, gt_role: departing}
- {name: Carson Kerce, person_id: 812668, gt_role: departing}
- {name: Alex Hernandez, person_id: 815415, gt_role: departing}
- {name: Parker Brosius, person_id: 702701, gt_role: departing}
- {name: Tate McKee, person_id: 806156, gt_role: departing}
- {name: Porter Buursema, person_id: 806040, gt_role: departing}
- {name: Isaiah Galason, person_id: 834497, gt_role: signee, slug: isaiah-galason, note: "Viewed as an unlikely-to-sign insurance pick — expected at GT barring a surprise before the July 27 deadline."}
```

- [ ] **Step 4: Create `pipeline/draft_registry.py`**

```python
"""Load and validate pipeline/draft.yaml (the 2026 MLB draft class)."""
import yaml

from pipeline.registry import RegistryError

VALID_GT_ROLE = {"departing", "signee"}


def load_draft(path, player_slugs):
    """player_slugs: set of slugs from players.yaml, for cross-linking validation."""
    with open(path) as f:
        entries = yaml.safe_load(f) or []
    seen = set()
    for e in entries:
        name = e.get("name")
        if not name:
            raise RegistryError(f"draft entry missing name: {e!r}")
        if name in seen:
            raise RegistryError(f"draft: duplicate name {name!r}")
        seen.add(name)
        if e.get("gt_role") not in VALID_GT_ROLE:
            raise RegistryError(f"draft: {name}: bad gt_role {e.get('gt_role')!r}")
        udfa = e.get("udfa")
        if udfa is not None:
            if not udfa.get("team"):
                raise RegistryError(f"draft: {name}: udfa entry needs team")
        elif not isinstance(e.get("person_id"), int):
            raise RegistryError(f"draft: {name}: needs numeric person_id (or udfa block)")
        rep = e.get("reported")
        if rep is not None and not (rep.get("bonus") and rep.get("source")):
            raise RegistryError(f"draft: {name}: reported needs bonus and source")
        slug = e.get("slug")
        if slug and slug not in player_slugs:
            raise RegistryError(f"draft: {name}: slug {slug!r} not in players registry")
    return entries
```

- [ ] **Step 5: Run** `.venv/bin/pytest pipeline/tests/test_draft_registry.py -q` — expect all PASS.
- [ ] **Step 6: Commit** `git add pipeline/draft.yaml pipeline/draft_registry.py pipeline/tests/test_draft_registry.py && git commit -m "feat(pipeline): draft.yaml registry + validation"`

### Task 2: Fetch + merge — draft_status.py

**Files:**
- Create: `pipeline/draft_status.py`
- Create: `pipeline/fixtures/draft/draft_2026.json` (trimmed live capture)
- Create: `pipeline/fixtures/draft/transactions_702701.json` (trimmed live capture)
- Test: `pipeline/tests/test_draft_status.py`

- [ ] **Step 1: Capture fixtures.** Trim real payloads (keep REAL structure — no hand-written JSON):

```bash
curl -s "https://statsapi.mlb.com/api/v1/draft/2026" -o /tmp/draft_full.json
# Trim with .venv/bin/python to: rounds 1 and 17 only, and within them only picks 3 (Lackey) and 496 (Galason)
# plus one signed non-GT pick that has a numeric signingBonus (pick 1) — save as pipeline/fixtures/draft/draft_2026.json
curl -s "https://statsapi.mlb.com/api/v1/transactions?playerId=702701&startDate=2026-07-01&endDate=2026-07-20" \
  -o pipeline/fixtures/draft/transactions_702701.json   # contains the real SGN entry dated 2026-07-14
```

- [ ] **Step 2: Write failing tests**

```python
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
    assert lackey["status"] == "unsigned"          # reported figure alone is not proof of signing
    galason = next(p for p in out["players"] if p["slug"] == "isaiah-galason")
    assert galason["status"] == "unsigned" and galason["note"] == "insurance pick"
    assert [p["name"] for p in out["udfa"]] == ["Mason Patel"]
    assert out["udfa"][0]["status"] == "signed_udfa"
    assert out["players"] == sorted(out["players"], key=lambda p: p["pick"])


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
```

- [ ] **Step 3: Run** `.venv/bin/pytest pipeline/tests/test_draft_status.py -q` — expect FAIL (module missing).

- [ ] **Step 4: Implement `pipeline/draft_status.py`**

```python
"""Merge MLB draft + transactions data with curated draft.yaml into draft.json."""
import requests

API = "https://statsapi.mlb.com/api/v1"
DEADLINE = "2026-07-27"    # ISO date; unsigned after this -> did_not_sign
_TIMEOUT = 30


def _get(url):
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _bonus(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def fetch_picks(year=2026):
    data = _get(f"{API}/draft/{year}")
    picks = {}
    for rd in data["drafts"]["rounds"]:
        for p in rd.get("picks", []):
            pid = (p.get("person") or {}).get("id")
            if pid:
                picks[pid] = {
                    "round": rd.get("round"), "pick": p.get("pickNumber"),
                    "team": (p.get("team") or {}).get("name"),
                    "slot": p.get("pickValue") or None,
                    "officialBonus": _bonus(p.get("signingBonus")),
                    "headshot": p.get("headshotLink"),
                }
    return picks


def fetch_signing(person_id, today):
    """Earliest official SGN transaction date since the draft window opened, or None."""
    data = _get(f"{API}/transactions?playerId={person_id}"
                f"&startDate=2026-07-01&endDate={today}")
    dates = [t.get("date") for t in data.get("transactions", [])
             if t.get("typeCode") == "SGN" and t.get("date")]
    return min(dates) if dates else None


def _status(signed, returning, today, deadline):
    if signed:
        return "signed"
    if returning:
        return "returning"
    if today > deadline:
        return "did_not_sign"
    return "unsigned"


def build_draft(entries, today, deadline=DEADLINE):
    picks = fetch_picks()
    players, udfa = [], []
    for e in entries:
        if e.get("udfa"):
            u = e["udfa"]
            udfa.append({"name": e["name"], "personId": None, "gtRole": e["gt_role"],
                         "slug": e.get("slug"), "round": None, "pick": None,
                         "team": u["team"], "slot": None, "bonus": None,
                         "bonusSource": None, "reportedSourceUrl": u.get("source"),
                         "status": "signed_udfa", "signedDate": u.get("date"),
                         "headshot": None, "note": e.get("note")})
            continue
        pid = e["person_id"]
        pick = picks.get(pid) or {}
        signed_date = fetch_signing(pid, today)
        official = pick.get("officialBonus")
        rep = e.get("reported") or {}
        signed = bool(signed_date) or official is not None
        bonus, source, rep_url = None, None, None
        if official is not None:
            bonus, source = official, "official"
        elif rep.get("bonus"):
            bonus, source, rep_url = rep["bonus"], "reported", rep["source"]
        players.append({"name": e["name"], "personId": pid, "gtRole": e["gt_role"],
                        "slug": e.get("slug"), "round": pick.get("round"),
                        "pick": pick.get("pick"), "team": pick.get("team"),
                        "slot": pick.get("slot"), "bonus": bonus,
                        "bonusSource": source, "reportedSourceUrl": rep_url,
                        "status": _status(signed, bool(e.get("returning")), today, deadline),
                        "signedDate": signed_date, "headshot": pick.get("headshot"),
                        "note": e.get("note")})
    players.sort(key=lambda p: p["pick"] if p["pick"] is not None else 10**6)
    return {"asOf": today, "players": players, "udfa": udfa}
```

- [ ] **Step 5: Run** `.venv/bin/pytest pipeline/tests/test_draft_status.py -q` — expect all PASS.
- [ ] **Step 6: Commit** `git add pipeline/draft_status.py pipeline/fixtures/draft/ pipeline/tests/test_draft_status.py && git commit -m "feat(pipeline): draft status fetch + merge"`

### Task 3: Wire into build_data with isolation

**Files:**
- Modify: `pipeline/build_data.py` (imports at line 7; add step after the league loop, before the final print at ~line 62; add `--draft` arg in `main()`)
- Test: `pipeline/tests/test_build_data.py` (append)

- [ ] **Step 1: Write failing tests** (append; mirror the file's existing fixture-platform setup for players/leagues paths — reuse its existing tmp-dir helpers/fixtures)

```python
def test_draft_json_written_and_isolated(tmp_path, monkeypatch, capsys):
    # Arrange a minimal draft.yaml + stubbed draft_status; use the existing
    # fixture-league players/leagues files from this test module's helpers.
    draft_yaml = tmp_path / "draft.yaml"
    draft_yaml.write_text("- {name: A, person_id: 1, gt_role: departing}\n")
    from pipeline import draft_status
    monkeypatch.setattr(draft_status, "build_draft",
                        lambda entries, today, deadline=draft_status.DEADLINE:
                        {"asOf": today, "players": [], "udfa": []})
    result = build_data.build(str(PLAYERS), str(LEAGUES), str(tmp_path / "out"),
                              str(tmp_path / "hist"), today="2026-07-20",
                              draft_path=str(draft_yaml))
    assert (tmp_path / "out" / "draft.json").exists()
    assert not any(k == "draft" for k, _ in result.failures)


def test_draft_failure_keeps_previous_file(tmp_path, monkeypatch, capsys):
    draft_yaml = tmp_path / "draft.yaml"
    draft_yaml.write_text("- {name: A, person_id: 1, gt_role: departing}\n")
    out = tmp_path / "out"; out.mkdir()
    (out / "draft.json").write_text('{"asOf": "2026-07-19", "players": [], "udfa": []}')
    from pipeline import draft_status
    def boom(entries, today, deadline=draft_status.DEADLINE):
        raise RuntimeError("api down")
    monkeypatch.setattr(draft_status, "build_draft", boom)
    result = build_data.build(str(PLAYERS), str(LEAGUES), str(out),
                              str(tmp_path / "hist"), today="2026-07-20",
                              draft_path=str(draft_yaml))
    assert ("draft", "api down") in [(k, e) for k, e in result.failures]
    assert '"2026-07-19"' in (out / "draft.json").read_text()   # previous file untouched
    assert "FAILED draft" in capsys.readouterr().err


def test_missing_draft_yaml_is_not_an_error(tmp_path):
    result = build_data.build(str(PLAYERS), str(LEAGUES), str(tmp_path / "out"),
                              str(tmp_path / "hist"), today="2026-07-20",
                              draft_path=str(tmp_path / "nope.yaml"))
    assert not any(k == "draft" for k, _ in result.failures)
```

(Adapt `PLAYERS`/`LEAGUES` to whatever fixture paths/helpers `test_build_data.py` already defines — read the file first and reuse its established setup verbatim.)

- [ ] **Step 2: Run** `.venv/bin/pytest pipeline/tests/test_build_data.py -q` — new tests FAIL (`build()` has no `draft_path`).

- [ ] **Step 3: Implement.** In `pipeline/build_data.py`: add `draft_registry, draft_status` to the `from pipeline import ...` line; add `import json, os` if absent. Change signature to `def build(players_path, leagues_path, out_dir, history_dir, today=None, draft_path="pipeline/draft.yaml"):`. After the league loop (before `records = output.assemble(...)`):

```python
    if os.path.exists(draft_path):
        try:
            d_entries = draft_registry.load_draft(draft_path, {p["slug"] for p in players})
            draft_json = draft_status.build_draft(d_entries, today)
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "draft.json"), "w") as f:
                json.dump(draft_json, f, indent=1)
            hist = os.path.join(history_dir, today)
            os.makedirs(hist, exist_ok=True)
            with open(os.path.join(hist, "draft.json"), "w") as f:
                json.dump(draft_json, f, indent=1)
        except Exception as e:  # noqa: BLE001 — same isolation ethos as leagues
            result.failures.append(("draft", str(e)))
            print(f"[build] FAILED draft: {e} — keeping previous data (if any)", file=sys.stderr)
```

In `main()`, add `ap.add_argument("--draft", default="pipeline/draft.yaml")` and pass `draft_path=args.draft`.

- [ ] **Step 4: Run** `.venv/bin/pytest -q` — full suite PASS.
- [ ] **Step 5: Commit** `git add pipeline/build_data.py pipeline/tests/test_build_data.py && git commit -m "feat(pipeline): draft.json in nightly build with failure isolation"`

### Task 4: Site data layer — lib/draft.ts + seed JSON

**Files:**
- Create: `site/src/data/draft.json` (empty seed so the static import always resolves)
- Create: `site/src/lib/draft.ts`
- Test: `site/tests/draft.test.ts`

- [ ] **Step 1: Seed** `site/src/data/draft.json`:

```json
{"asOf": null, "players": [], "udfa": []}
```

- [ ] **Step 2: Write failing tests** (`site/tests/draft.test.ts`)

```ts
import { describe, expect, it } from 'vitest';
import { fmtMoney, getDraft, STATUS_LABEL } from '../src/lib/draft';

describe('draft data', () => {
  it('loads the draft file with players and udfa arrays', () => {
    const d = getDraft();
    expect(Array.isArray(d.players)).toBe(true);
    expect(Array.isArray(d.udfa)).toBe(true);
  });

  it('maps every status to a label', () => {
    expect(STATUS_LABEL.signed).toBe('Signed');
    expect(STATUS_LABEL.unsigned).toBe('Unsigned');
    expect(STATUS_LABEL.returning).toBe('Returning to GT');
    expect(STATUS_LABEL.did_not_sign).toBe('Did not sign');
    expect(STATUS_LABEL.signed_udfa).toBe('Signed (UDFA)');
  });

  it('formats money and em-dashes null', () => {
    expect(fmtMoney(9740100)).toBe('$9,740,100');
    expect(fmtMoney(null)).toBe('—');
  });
});
```

- [ ] **Step 3: Run** `cd site && npm test` — draft tests FAIL (module missing).

- [ ] **Step 4: Implement `site/src/lib/draft.ts`** (match data.ts style)

```ts
import draftJson from '../data/draft.json';

export type DraftStatus = 'signed' | 'unsigned' | 'returning' | 'did_not_sign' | 'signed_udfa';

export interface DraftPlayer {
  name: string;
  personId: number | null;
  gtRole: 'departing' | 'signee';
  slug: string | null;
  round: string | null;
  pick: number | null;
  team: string | null;
  slot: number | null;
  bonus: number | null;
  bonusSource: 'official' | 'reported' | null;
  reportedSourceUrl: string | null;
  status: DraftStatus;
  signedDate: string | null;
  headshot: string | null;
  note: string | null;
}

export interface DraftData {
  asOf: string | null;
  players: DraftPlayer[];
  udfa: DraftPlayer[];
}

export const STATUS_LABEL: Record<DraftStatus, string> = {
  signed: 'Signed',
  unsigned: 'Unsigned',
  returning: 'Returning to GT',
  did_not_sign: 'Did not sign',
  signed_udfa: 'Signed (UDFA)',
};

export function getDraft(): DraftData {
  return draftJson as DraftData;
}

export function fmtMoney(n: number | null): string {
  return n == null ? '—' : '$' + n.toLocaleString('en-US');
}
```

- [ ] **Step 5: Run** `cd site && npm test` — PASS. `npm run build` — 43 pages, PASS (page not added yet; proves the seed import is safe).
- [ ] **Step 6: Commit** `git add site/src/data/draft.json site/src/lib/draft.ts site/tests/draft.test.ts && git commit -m "feat(site): draft data layer + empty seed"`

### Task 5: /draft page + nav link

**Files:**
- Modify: `site/src/components/Nav.astro:2-5` (links array)
- Create: `site/src/pages/draft.astro`

- [ ] **Step 1: Nav link.** In `Nav.astro` change the links array to:

```ts
const links = [
  { href: '/', label: 'Players' },
  { href: '/draft', label: 'Draft' },
  { href: '/leagues', label: 'Leagues' },
];
```

- [ ] **Step 2: Create `site/src/pages/draft.astro`**

```astro
---
import Headshot from '../components/Headshot.astro';
import Base from '../layouts/Base.astro';
import { fmtMoney, getDraft, STATUS_LABEL } from '../lib/draft';
import { getPlayer } from '../lib/data';

const draft = getDraft();
const anyUnsigned = draft.players.some((p) => p.status === 'unsigned');
---
<Base title="2026 MLB Draft — GT Summer Tracker">
  <h1>2026 MLB Draft — Georgia Tech</h1>
  <p class="sub">
    GT's draft class: who signed, for how much, and who's headed (back) to campus.
    {anyUnsigned && <span class="deadline">Signing deadline: July 27, 5 p.m. ET</span>}
    {draft.asOf && <span class="asof">Updated {draft.asOf}</span>}
  </p>

  {draft.players.length === 0 && <p class="empty">Draft data loads with the next nightly refresh.</p>}

  {draft.players.length > 0 && (
    <div class="scroll">
      <table>
        <thead>
          <tr><th>Pick</th><th>Player</th><th>Drafted by</th><th>Slot value</th><th>Bonus</th><th>Status</th></tr>
        </thead>
        <tbody>
          {draft.players.map((p) => {
            const reg = p.slug ? getPlayer(p.slug) : undefined;
            return (
              <tr>
                <td class="pick">R{p.round} · #{p.pick}</td>
                <td class="player">
                  {reg
                    ? <Headshot name={p.name} photo={reg.photo} size={32} />
                    : (p.headshot ? <img class="hs" src={p.headshot} alt="" width="32" height="32" loading="lazy" /> : <Headshot name={p.name} photo={null} size={32} />)}
                  <span class="pcell">
                    {p.slug ? <a href={`/players/${p.slug}`}>{p.name}</a> : p.name}
                    <span class="role">{p.gtRole === 'signee' ? 'Incoming signee' : 'GT 2026'}</span>
                    {p.note && <span class="pnote">{p.note}</span>}
                  </span>
                </td>
                <td>{p.team ?? '—'}</td>
                <td class="num">{fmtMoney(p.slot)}</td>
                <td class="num">
                  {fmtMoney(p.bonus)}
                  {p.bonusSource === 'reported' && p.reportedSourceUrl &&
                    <a class="reported" href={p.reportedSourceUrl} rel="noopener">reported</a>}
                </td>
                <td><span class={`chip ${p.status}`}>{STATUS_LABEL[p.status]}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  )}

  {draft.udfa.length > 0 && (
    <section class="quiet">
      <h2 class="section-title">Undrafted free agents</h2>
      <p>
        {draft.udfa.map((p, i) => (
          <>
            <span>{p.name}</span>
            <span class="where"> — {p.team}{p.signedDate ? `, signed ${p.signedDate}` : ''}</span>
            {p.reportedSourceUrl && <> (<a href={p.reportedSourceUrl} rel="noopener">source</a>)</>}
            {i < draft.udfa.length - 1 ? ' · ' : ''}
          </>
        ))}
      </p>
    </section>
  )}
</Base>

<style>
  h1 { margin: 0 0 2px; font-size: 24px; }
  .sub { margin: 0 0 18px; color: var(--text-mut); font-size: 14px; }
  .deadline { margin-left: 10px; color: var(--navy); font-weight: 600; }
  .asof { margin-left: 10px; font-size: 12px; }
  .empty { color: var(--text-mut); font-size: 14px; }
  .scroll { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th { text-align: left; font-size: 12px; color: var(--text-mut); border-bottom: 2px solid var(--line); padding: 6px 10px; }
  td { border-bottom: 1px solid var(--line); padding: 8px 10px; vertical-align: middle; }
  .pick { white-space: nowrap; color: var(--text-mut); }
  .player { display: flex; align-items: center; gap: 10px; min-width: 220px; }
  .hs { border-radius: 50%; object-fit: cover; background: var(--line); }
  .pcell { display: flex; flex-direction: column; }
  .role { font-size: 11px; color: var(--text-mut); }
  .pnote { font-size: 12px; color: var(--text-mut); font-style: italic; max-width: 380px; }
  .num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .reported { margin-left: 6px; font-size: 11px; color: var(--text-mut); text-decoration: underline dotted; }
  .chip { font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
  .chip.signed, .chip.signed_udfa { background: #e2efe4; color: #1e5b2a; }
  .chip.unsigned { background: #eef1f5; color: #5b6472; }
  .chip.returning { background: var(--navy); color: var(--gold); }
  .chip.did_not_sign { background: #f3e9e9; color: #7a3535; }
  .quiet { margin-top: 26px; }
  .quiet p { font-size: 13px; line-height: 2; margin: 0; }
  .where { color: var(--text-mut); }
</style>
```

Check chip contrast (≥4.5:1): `#1e5b2a` on `#e2efe4`, `#5b6472` on `#eef1f5` (5.28:1, already used), `--gold` on `--navy` (existing nav pairing), `#7a3535` on `#f3e9e9` — verify each with a contrast checker; darken text colors if any fall short.

- [ ] **Step 3: Verify empty-state build.** `cd site && npm run build` — expect 44 pages (new /draft with the "loads with the next nightly refresh" empty state, since the seed is empty). `npm test` still green.
- [ ] **Step 4: Commit** `git add site/src/components/Nav.astro site/src/pages/draft.astro && git commit -m "feat(site): /draft page + nav link"`

### Task 6: Live cutover, verify, deploy

- [ ] **Step 1: Live build.** `.venv/bin/python -m pipeline.build_data` — expect `0 league failure(s)` and no `FAILED draft` line; `site/src/data/draft.json` now has 9 players (asOf today).
- [ ] **Step 2: Sanity-check the JSON against reality.** `cat site/src/data/draft.json | .venv/bin/python -m json.tool | head -40` — Lackey R1 #3 Twins slot $9,740,100; Brosius status `signed`, signedDate `2026-07-14`; Galason slug + note present; statuses of unsigned players are `unsigned` (or `did_not_sign` if run after 7/27 — both correct).
- [ ] **Step 3: Full suites.** `.venv/bin/pytest -q` (expect ~110 passed) and `cd site && npm test && npm run build` (44 pages).
- [ ] **Step 4: Visual check.** Serve or inspect `dist/draft/index.html` — table renders, chips colored, Galason links to his profile, headshots load (MLB draft headshot URLs are external — confirm they render; if any 404s, the Headshot fallback shows initials).
- [ ] **Step 5: Commit + push.** `git add site/src/data/draft.json data/ && git commit -m "feat: draft tracker live data" && git push` (nightly bot may have pushed — `git pull --ff-only` first; regenerate if pulled). Vercel deploys from main; verify `https://gt-sports-tracking.vercel.app/draft` renders with live data and the nav shows Draft.
- [ ] **Step 6: Consistency note.** The scheduled daily-draft-signing-check task (already created) starts updating `pipeline/draft.yaml` curated fields once this lands — no action needed here beyond confirming draft.yaml exists on main.
