---
target: 2027 outlook tab
total_score: 25
max_score: 36
na_heuristics: 9
p0_count: 0
p1_count: 3
timestamp: 2026-07-23T00-33-18Z
slug: site-src-pages-outlook-astro
---
Method: dual-agent (A: isolated design-review subagent · B: isolated detector/browser-evidence subagent)

Page state at review time: Lackey signed today, so the "Unsigned draftees · deadline Jul 27" column self-removed — the page renders a three-column ledger (19 Returning / 21 Arriving / 9 Signed pro). Galason (drafted, unsigned signee) sits in Arriving with the amber tag.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Jul 27 deadline exists only in hover titles; no as-of stamp near percentile chips |
| 2 | Match System / Real World | 4 | Real ballpark, real distances, honest baseball grammar — solid |
| 3 | User Control and Freedom | 3 | Static read-only surface; nothing traps |
| 4 | Consistency and Standards | 2 | Legend ≠ field encoding; three renderings of "arriving" ring; circles in lists after circles were retired |
| 5 | Error Prevention | 3 | Fixture-league guard + self-removing empty column — graceful |
| 6 | Recognition Rather Than Recall | 2 | Chips mix OPS/ERA percentiles unlabeled; "UTIL · 4" occluded; "2026 team" tag cryptic |
| 7 | Flexibility and Efficiency | 3 | Counts-first is efficient; no intra-column filter (acceptable) |
| 8 | Aesthetic and Minimalist Design | 4 | Dense, composed, zero chrome waste |
| 9 | Error Recovery | n/a | Static page; no error states can occur |
| 10 | Help and Documentation | 2 | All explanation lives in hover-only `title` attrs — invisible to touch/keyboard |
| **Total** | | **25/36** | **Acceptable (69%) — strong bones, integrity slips** |

## Design Specificity Verdict

**LLM assessment (unanchored):** Authored, not interchangeable — the most GT-specific surface on the site. Mac Nease drawn from its real wall numbers, position groups where they play, pitchers honestly off the grass, count-led ledger in the system's voice, provenance tags never touching the ramp. Two dilutions: arriving players' mixed non-GT jerseys make the field partly a stranger yearbook (honest, but the one place the display fights identity), and the field's faces are anonymous on desktop, so the signature display can't caption its own story.

**Deterministic scan:** CLI scan of the five source files: **clean (0 findings)**. The in-page runtime detector told a different story: **61 element-level findings** — ~46 × 10px text (bench `.sname` names, `.ptag` provenance chips, `.tail.tag` round tags — below the detector's 11px floor *and* DESIGN.md's own label floor), 9 × measured contrast failure (Signed-pro round tags: `#6b7280` on `#eef1f5` = 4.3:1, under AA 4.5:1 — a surface the ramp contrast test does not cover), 6 × uppercase full sentences (field tooltip subtitles), 1 × tooltip clipping risk at the `.field-crop` overflow edge. One false positive: "overused font: helvetica" — the system stack is mandated by CLAUDE.md.

**Visual overlays:** injection was verified (61 overlays rendered and were screenshot-captured in a separate tab); the tab was cleared after evidence capture, so no overlay remains open. Live server confirmed stopped.

## Overall Impression

The page's bones are the best on the site: the field is a real signature display, and 19 / 21 / 9 answers the roster question in seconds. What holds it back is integrity of the details — the legend contradicts the encoding it explains, the page's central drama (the Jul 27 deadline) is invisible except on hover, and the smallest text on the page is exactly where the detector measured real floor and contrast violations. The single biggest opportunity: let the field carry names (and possibly form), so the signature display becomes the screenshot that sells the site.

## What's Working

1. **The field earns its space** — a positional canvas carrying real depth-chart data ("OF · 3" tells the thin-outfield story; "C · 4" the surplus). No decoration.
2. **The provenance tag grammar** — "▸ JAX STATE" navy tags, gold FR, amber limbo, and silence for returning players make a 21-item Arriving column scannable in one pass without touching the ramp.
3. **Count-led ledger** — 44px numerals answer the 5-second question; Returning sorts best-first so the good news leads (Lewis 96, Angelakos 87).

## Priority Issues

- **[P1] The signature display's encoding slips.** "UTIL · 4" is painted over by the IF cluster on desktop (zone stacking), so four players sit in an unlabeled band; the legend says navy ◌ arriving but the field draws arriving as *white* dashed rings and the staff panel as *navy* dashed — three renderings of one distinction on one card. **Why:** the field is the page's authority; when its own key misleads, trust leaks exactly where the site stakes it. **Fix:** z-index the zone tags above chips; unify the arriving ring (navy-bright dashed everywhere); draw legend swatches as mini bust-frames rather than typographic dots. *Suggested command: /impeccable polish.*
- **[P1] The deadline is invisible.** With the limbo column self-removed, "Jul 27" survives only in Galason's hover title. Touch and keyboard users never learn why his tag is amber or what resolves it — on a page subtitled by the draft resolving. **Fix:** put the numeral in the tag ("DRAFTED · UNSIGNED · JUL 27") and keep a terse visible stamp while any draftee is unsigned; archive gracefully after the deadline. *Suggested command: /impeccable clarify.*
- **[P1] Accessibility debt, now measured.** `role="img"` on `.field` wraps ~20 interactive links (ARIA makes children of img presentational — ATs may flatten the whole subtree); ~90 tab stops with no in-page skip; every `title`-only explanation unreachable by keyboard; 46 × 10px text; 9 × 4.3:1 tags; 26×32px tap targets on mobile field busts. **Fix:** drop role="img" for a labeled group/figure, add a skip link past the field, raise 10px → 11px floor site-wide on these labels, darken `--text-mut`-on-`--line-soft` tags one step, enlarge mobile hit areas. *Suggested command: /impeccable audit → polish.*
- **[P2] Percentile chips carry no metric and no receipt.** 96 (OPS %ile) and 87 (ERA %ile) sit unlabeled in one column; nothing says "through Jul 22." Brushes the every-figure-keeps-its-receipt rule. **Fix:** one muted line under the Returning rule — "summer percentile · OPS / ERA · through Jul 22" — plus per-chip title/aria (PercentileChip already supports `metric`). *Suggested command: /impeccable clarify.*
- **[P2] Spec drift: circle headshots in the ledger lists.** DESIGN.md (revised 2026-07-22) declares busts universal and circles retired; outlook's three columns still render circles. **Fix:** `variant="bust"` at list size; audit leagues page too. *Suggested command: /impeccable polish.*

## Persona Red Flags

**Alex (stat-head):** unlabeled mixed-metric chip column is his first complaint; Signed pro omits the money (draft.json holds sourced bonuses — today's $9.5M Lackey number isn't on this page, only "R1"); no way to split Arriving 11 transfers / 10 freshmen without reading 21 tags.

**Sam (screen reader / keyboard):** the role="img"-wrapping-links structure is invalid ARIA; the tab gauntlet is ~90 stops with every player visited twice (field, then ledger); tooltips do appear on :focus-visible (genuinely good), but all `title`-attribute context (full school names, the deadline) never reaches him; 10px labels sit below the project's own floor.

**GT diehard at lunch (phone):** the 5-second answer works at 375px, but on-field busts are 26×32px targets at 2px gaps — tapping the right face is a lottery, and since tap navigates, the tooltip layer simply doesn't exist on touch; the screenshot they'd send the group chat has no names on it.

## Minor Observations

- At 1280×1000 the field fills the viewport; the 19/21/9 numerals sit below the fold — the counts lose their first-glance moment.
- Ten Returning rows are chipless with no cue why (the reason exists in `note` but isn't surfaced).
- The foul-ground corners of the field card are dead space at desktop width — room for the legend or counts.
- "2026 team" tag on draft-withdrawal rows (path empty today) is opaque; "withdrew · returning" reads better.
- The page *ends* on "9 Signed pro" with a UDFA as the literal last row — the fan closes the tab on the losses; and nobody adds 19+21 for them (no roster-total synthesis anywhere).
- Uppercase full-sentence tooltips ("INCOMING TRANSFER FROM JACKSONVILLE STATE…") — sentence-case would read better and satisfy the detector's all-caps-body rule.
- Tooltip clipping risk where `.field-crop` overflow:hidden meets edge-positioned chips.

## Improvement Brainstorm (all data already in players.json / draft.json — no fake data)

1. **Names on the field (S/M).** 11px last-name labels under each on-field bust, as the staff panel already does. The signature display becomes self-captioning — the group-chat screenshot finally names its subjects.
2. **Summer form on the field (M).** Pin each on-field bust with its existing PercentileChip (real leagues only; `summerPct` is already computed on this page). One frame then answers both core questions: next year's team *and* how their summer is going. The screenshot that sells the site.
3. **Signing receipts in the ledger (S).** Signed-pro rows gain the bonus numeral linked to its source: "R1 · $9.5M" (bonus + bonusSource + reportedSourceUrl preserved). Today's biggest number becomes visible where the fan lands.
4. **Roster math strip (S).** One length-encoded bar above the ledger: 19 returning (gold) + 21 arriving (navy) = 40 projected, amber sliver for the unsigned one — the synthesis moment the page lacks, labeled numerals only.
5. **Deadline stamp with archival degrade (S).** "· JUL 27" in the amber tags plus a terse stamp while anyone is unsigned; after the deadline the limbo machinery archives into "how the class signed."
6. **Class-year balance bar (M).** Stacked length bar of the projected 2027 roster by class (FR/SO/JR/SR from classYear on all 40) — answers "are we young next year?", which no column currently does. Categorical colors, never the ramp.

## Questions to Consider

1. The page ends on the departed. Should the ledger read losses-first, future-last, so the fan closes the tab on next year's team?
2. Galason hasn't signed with GT's future — yet he stands on the 2027 field, inside "IF · 9" and "21 arriving." Is the dashed ring honest enough, or should the no-fake-data instinct keep him (and the count) visibly conditional until Jul 27?
3. The field says *who*; the ledger says *how good*. Is one-encoding-per-surface the discipline that keeps this Savant-grade — or is the field with percentile chips the moment this page stops being a depth chart and becomes the franchise display?
