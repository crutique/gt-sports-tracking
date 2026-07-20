# Draft Watch — Automated Signing-News Watcher ("our own Spotrac")

**Date:** 2026-07-20 · **Status:** Approved by owner (scope: full cloud watcher; cadence: every 6 h; provenance: three-tier unverified/reported/official) · **Extends:** docs/superpowers/specs/2026-07-20-draft-tracker-design.md

## Goal

Detect draft-signing news ahead of MLB's official records with no human in the loop, publishing with honest provenance. Missed-Kerce lesson: reporting runs days ahead of MLB's data; the desktop routine only runs while the owner's app is open. This watcher runs in GitHub Actions 24/7.

## Three-tier bonus provenance

| Tier | Written by | Site rendering | Implies Signed? |
|---|---|---|---|
| `official` | MLB StatsAPI `signingBonus` (existing) | plain `$1,900,000` | yes |
| `reported` | Curation (routine/owner) OR watcher when source is on the trusted whitelist | amount + "reported" source link (existing style) | yes |
| `unverified` | Watcher, non-whitelisted source, definitive claim + dollar figure | amount + muted "unverified" source link (new, visually more tentative; AA contrast) | **no** — chip stays Unsigned until promoted |

Hedged claims ("expected to sign", rumors) never publish — flags file only. Precedence for the displayed figure: official > reported > unverified. Never overwrite an existing higher tier; never downgrade.

**Trusted whitelist (v1):** mlb.com, milb.com, mlbtraderumors.com, si.com, espn.com, theathletic.com, ajc.com, official team domains (dbacks/twins/athletics/braves/rays/marlins/angels/nationals via mlb.com team paths). Everything else (gtswarm.com, blogs, unknown outlets) → unverified at best.

## Components

### 1. Registry schema (`pipeline/draft.yaml` + `pipeline/draft_registry.py`)

New optional per-entry block, written by the watcher, adjudicated by the routine:

```yaml
unverified: {bonus: 1900000, source: "https://...", detected: "2026-07-21"}
```

Validation mirrors `reported:`: `bonus` int required, `source` required, `detected` ISO date string required. An entry may hold both `reported` and `unverified` (reported wins; the routine deletes stale unverified blocks).

### 2. Pipeline merge (`pipeline/draft_status.py`)

- `bonusSource` gains `'unverified'`; JSON carries `unverifiedSourceUrl` when applicable (mirror of `reportedSourceUrl`).
- Signed resolution unchanged: SGN transaction, official bonus, or reported bonus. Unverified does NOT imply signed.
- Display-figure precedence: official > reported > unverified.

### 3. News scanner (`pipeline/news_scan.py`)

Pure functions + one LLM seam. For each open player (status not signed, or signed without official bonus):

- **Fetch** (browser User-Agent, per-source failure isolation): Google News RSS `https://news.google.com/rss/search?q="<name>"+baseball` (parse `<item>` title/link/pubDate); the MLB.com signing-tracker article; GTSwarm draft thread latest 2 pages (`https://gtswarm.com/threads/2026-mlb-draft.31400/` — discover last page from page-1 pagination markup). Strip HTML → snippets containing the player's last name (±300 chars).
- **Extract** — `_extract(snippets, player)` calls the Anthropic API (model `claude-haiku-4-5-20251001`, temperature 0, max ~500 tokens) with a strict prompt returning JSON: `{event: "signed"|"expected"|"rumor"|"none", amount: int|null, source_url, quote}`. The call sits behind a module-level seam (like `_get` in the scrapers) so tests mock it. Malformed model output → treated as `none` (never crashes the run).
- **Policy** — `decide(extraction, whitelist)` (pure, exhaustively unit-tested):
  - `signed` + amount + whitelisted domain → write/refresh `reported:`
  - `signed` + amount + non-whitelisted → write `unverified:` (skip if identical source URL already present)
  - `signed` without amount, or `expected`/`rumor` → append `{player, event, source_url, quote, seen}` to `data/draft-watch-flags.json` (deduped by source URL)
  - `none` → nothing
  - Guards: exact player-name match required in the quote; never touch entries that already have `official` bonus or an equal/higher tier from the same source class.

### 4. Orchestrator (`pipeline/draft_watch.py`, CLI `python -m pipeline.draft_watch`)

1. Date gate: exit 0 quietly outside `DRAFT_WATCH_WINDOW` (2026-06-10 → 2026-08-05, module constants; next season bump them).
2. Refresh official signals + regenerate `site/src/data/draft.json` via the existing `draft_registry`/`draft_status` path (this alone gets official signings live within 6 h).
3. Run the news scanner for open players; apply policy → edits to `pipeline/draft.yaml` (ruamel-free: targeted line edits preserving flow style, or yaml round-trip — implementer follows the file's single-line-entry convention) and/or the flags file.
4. Exit code 0 on success (even with per-source fetch failures — log them); nonzero only on total failure. Print a one-line summary (`[watch] official=1 reported=0 unverified=1 flags=2 skipped-sources=[...]`).

### 5. Workflow (`.github/workflows/draft-watch.yml`)

Cron `0 */6 * * *` + `workflow_dispatch`. Steps: checkout, Python setup, `pip install -r requirements.txt`, `python -m pytest -q` (offline gate), `python -m pipeline.draft_watch` with `ANTHROPIC_API_KEY` from repo secrets, then commit `pipeline/draft.yaml site/src/data/draft.json data/` if changed (same bot-commit pattern as nightly) → push → Vercel deploys. If the secret is absent, the news-scan step is skipped with a visible warning (official refresh still runs).

### 6. Site (`site/src/lib/draft.ts` + `site/src/pages/draft.astro`)

- `bonusSource: 'official' | 'reported' | 'unverified' | null`; `unverifiedSourceUrl: string | null`.
- Bonus cell: unverified renders the amount + an "unverified" link styled distinctly muted (e.g. lighter text + dotted underline, italic); contrast ≥ 4.5:1. Status chip unchanged (Unsigned).

### 7. Routine integration

The scheduled desktop routine's prompt gains: each run, adjudicate every `unverified:` block and `data/draft-watch-flags.json` entry — promote to `reported:` (best source), or delete with a dated comment; clear handled flags.

## Ops & cost

- **Owner setup (required):** add `ANTHROPIC_API_KEY` to the GitHub repo's Actions secrets. Without it the watcher still ships official signals.
- Cost: ≤ ~20 Haiku calls × 4 runs/day ≈ cents/day, only inside the season window.
- Kill switch: disable the workflow in the Actions UI, or the window constants.

## Testing

- All policy/merge/schema behavior fixture-tested offline (LLM seam mocked; RSS/HTML fixtures trimmed from live captures — include a real Google News RSS sample and a GTSwarm page slice).
- One live end-to-end validation at cutover: run `python -m pipeline.draft_watch` locally with the real key; verify the summary line, that no false entry was written for already-resolved players (Brosius/Kerce), and that draft.json regenerated.
- Workflow validated via `workflow_dispatch` on GitHub after the secret is added.

## Success criteria

- An official signing appears on the site within 6 h of MLB's record (vs overnight today).
- A whitelisted-outlet report auto-publishes as `reported` (Signed) within 6 h; a fan-board figure appears as `unverified` (still Unsigned) within 6 h; hedged talk publishes nothing.
- Zero writes that downgrade or overwrite a higher tier; re-runs are idempotent (no duplicate blocks/flags).
- Suites green; the watcher's failure never breaks the nightly build or the site (separate workflow, isolated commits).

## Out of scope (v1)

X/Twitter and Spotrac/Baseball America scraping (blocked surfaces); non-draft news (trades, injuries); multi-year generalization beyond the window constants; notifications beyond the flags file.
