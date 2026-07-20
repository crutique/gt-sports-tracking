# MLB Draft Tracker — Design

**Date:** 2026-07-20 · **Status:** Approved by owner (scope, placement, data model, bonus sourcing) · **Feature:** track GT's 2026 MLB Draft class — who signed, for how much, and who is coming (back) to GT.

## Goal

GT fans following the site want three answers per drafted player: did he sign with the team that drafted him, for how much, and — if not — has he declared he's playing at GT in 2027? The tracker must stay current with zero routine manual work for the machine-readable parts, and clearly-labeled curation for the news-driven parts.

## Scope: who is covered

The **full 2026 GT draft class**, three groups:

1. **Drafted off the GT roster** (all departing): Vahn Lackey (R1 #3, Twins, person 822518), Drew Burress (R1 #8, Athletics, 806039), Jarren Advincula (R2 #45, Angels, 814181), Carson Kerce (R2 #53, D-backs, 812668), Alex Hernandez (R5 #143, Athletics, 815415), Parker Brosius (R9 #262, Braves, 702701), Tate McKee (R10 #293, Rays, 806156), Porter Buursema (R16 #475, Marlins, 806040).
2. **Drafted incoming signees**: Isaiah Galason (R17 #496, Nationals, 834497, tracker slug `isaiah-galason`). A research sweep confirms whether any other 2026 GT signee/commit was drafted (signees carry their HS as `school` in the draft API, so name/commit-list research is required — school filtering cannot find them).
3. **Undrafted free agents**: Mason Patel (RHP, reported UDFA signing with the Athletics — details to be verified in the research sweep). UDFA players have no draft-API record; their entries are fully curated.

Out of scope: historical drafts (2026 only), a homepage teaser (dedicated page only), non-GT players.

## Data sources (verified 2026-07-20)

| Signal | Source | Latency | Notes |
|---|---|---|---|
| Signed yes/no + date | StatsAPI transactions feed (`typeCode=SGN`), queried per person id | Same day (verified: Brosius SGN dated 7/14) | No dollar amount |
| Official bonus + slot value | StatsAPI `draft/2026` picks: `signingBonus`, `pickValue` | Days behind reporting (6 of top 40 vs ~26 editorially known) | Authoritative once present |
| Reported bonus | Jim Callis (MLB Pipeline) / Baseball America / Spotrac reporting | Minutes–hours | Not machine-readable; entered as curated `reported:` with source URL |
| Return-to-GT declarations | News/social (GTSwarm, On3, beat writers) | n/a | Curated `returning:` + `note` with source |

Spotrac is an aggregator of the same reporting and is Cloudflare-protected; it is used as a human reference, never scraped.

## Component 1 — curated registry: `pipeline/draft.yaml`

One list, one entry per player. Minimal by design — everything derivable from the API by person id stays out of the file.

```yaml
- {name: Vahn Lackey, person_id: 822518, gt_role: departing}
- {name: Isaiah Galason, person_id: 834497, gt_role: signee, slug: isaiah-galason}
- {name: Mason Patel, gt_role: departing, udfa: {team: Athletics, date: "2026-07-15", source: "https://..."}}
```

Optional per-entry curation fields:
- `reported: {bonus: 9500000, source: "https://x.com/jimcallisMLB/..."}` — reporter-broken figure, shown with a "reported" label until the official amount lands.
- `returning: true` + `note: "..."` — news-driven declaration (either direction; `note` also covers nuance like "expected to sign").
- `slug` — links the row to a tracker profile (signees only).

Validation (mirrors registry.py conventions): unique names; `gt_role` ∈ {departing, signee}; every non-UDFA entry needs a numeric `person_id`; UDFA entries need `udfa.team`; `slug` must exist in players.yaml.

## Component 2 — pipeline: `pipeline/draft_status.py`

Runs inside the nightly `build_data` flow (same cron, same commit step):

1. Fetch `GET statsapi.mlb.com/api/v1/draft/2026` once → per person id: round, pickNumber, team, pickValue, signingBonus, headshotLink.
2. Fetch `GET /api/v1/transactions?playerId={id}&startDate=2026-07-01&endDate=<today>` per drafted person id → signed flag + signing date from the earliest SGN entry.
3. Merge with draft.yaml. Bonus precedence: **official `signingBonus` > curated `reported.bonus`**; the JSON carries `bonus`, `bonusSource` (`official` | `reported`), and `reportedSourceUrl` when applicable.
4. Status resolution, in order: `signed` (SGN transaction, official bonus, or curated reported bonus — reporters publish figures only for agreed deals) → `returning` (curated `returning: true`) → after the deadline (2026-07-27 17:00 ET) `did_not_sign` → else `unsigned`. UDFA entries are always `signed_udfa`.
5. Output `data/draft.json` + `site/src/data/draft.json` (players sorted by pickNumber; UDFA last). Any fetch failure keeps the previous file and prints a `[build] FAILED draft:` line — same carry-forward ethos as leagues; a missing previous file is not an error (feature bootstraps empty).

Tests (offline, fixture-based, TDD): API fixture merge; transactions→signed flip; reported-vs-official precedence (and official replacing reported); deadline flip pre/post 7/27 (deadline injected, not read from the wall clock, so tests are date-stable); UDFA passthrough; yaml validation errors; carry-forward on fetch failure.

## Component 3 — site: `/draft` page

- Nav gains a "Draft" link (Base layout, alongside Leagues).
- Header: "2026 MLB Draft — Georgia Tech" + a deadline line ("Signing deadline: July 27, 5 p.m. ET") shown until the deadline passes.
- Table sorted by pick: **Rd-Pick · headshot · Player · Pos · Drafted by · Slot value · Bonus · Status**.
  - Headshots: draft API `headshotLink` for departing players; registry photo for signees. Broken/missing image falls back to the site's existing placeholder treatment.
  - Player name links to the tracker profile when `slug` present (Galason).
  - Bonus cell: `$9,740,100` for official; `$9.5M reported` with the label linking the source when curated; `—` when unsigned.
  - Status chip: **Signed / Unsigned / Returning to GT / Did not sign** (+ Signed (UDFA) in the section below). Colors follow existing chip conventions; contrast ≥ 4.5:1.
  - `note` renders as a muted line under the player name, like profile notes.
- UDFA section beneath the table, same row shape minus draft columns.
- Vitest: draft.json loader typing + status/label mapping. Astro build must pass with an empty/absent draft.json (pre-bootstrap).

## Operations: daily research & signing verification

Two halves, matching the hybrid data model:

- **Automated (no human):** the existing nightly GitHub Actions run picks up transaction signings and official bonuses every night and redeploys. Nothing new to operate.
- **Curated (agent-assisted):** a **daily scheduled research routine** (owner-approved separately) through **Aug 1**: check the 9 draftees' transactions/draft records for changes, sweep reporting (Callis/BA/Spotrac/GTSwarm/On3/local news) for bonus figures and return declarations, and — only when something changed — update draft.yaml (+ the summer registry when relevant), run the test suites, commit and push. The same routine carries the already-flagged late-July checks: UDFA/late summer-club signings for the undrafted returnees (Zuckerman, Baker, Shadek, Ballard, Loy, Lankie, Gunther, Blauser, Morgan) and Galason's July 27 sign-or-campus resolution. After Aug 1 the routine winds down to weekly, then off once the class is fully resolved.

## Research prerequisites (before or during implementation)

1. Sweep the full 2026 GT signee/commit list for additional draftees beyond Galason.
2. Verify Mason Patel's UDFA signing (team, date, source).
3. Verify Brosius's official `signingBonus` of `500` (string) against reporting — plausible senior-sign amount, but confirm it isn't an API data quirk before displaying.

## Success criteria

- /draft page lists the full class with correct round/pick/team/slot data from the API, byte-consistent with `statsapi.mlb.com/api/v1/draft/2026`.
- A new signing appears on the site no later than the first nightly run after MLB's transaction posts, with no human involvement.
- Reported bonuses are visibly labeled and sourced; official amounts replace them automatically.
- After July 27, no player shows "Unsigned"; unsigned players read "Did not sign" (or "Returning to GT" when declared).
- Suites green: pytest (new draft tests), vitest, Astro build — including the empty-draft.json bootstrap case.
