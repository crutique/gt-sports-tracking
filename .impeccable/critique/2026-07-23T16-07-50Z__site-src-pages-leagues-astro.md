---
target: By League tab (/leagues)
total_score: 18
max_score: 28
na_heuristics: 5,9,10
p0_count: 0
p1_count: 2
timestamp: 2026-07-23T16-07-50Z
slug: site-src-pages-leagues-astro
---
Method: dual-agent (A: design-review · B: detector+browser evidence)

# Critique — "By League" tab (`/leagues`)

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Freshness stamp is honest but lives only in the global footer; no per-card "stats through" stamp. |
| 2 | Match System / Real World | 2 | Bare chips: red=good (Savant) with no on-screen key; metric (OPS/ERA) and population unnamed. |
| 3 | User Control and Freedom | 3 | Read-only, clean exits; nothing traps the user. |
| 4 | Consistency and Standards | 3 | Reuses shared components, but chip *authority* mismatches DESIGN.md (solid here vs. muted for summer snapshots). |
| 5 | Error Prevention | n/a | No inputs/forms/destructive actions. |
| 6 | Recognition Rather Than Recall | 2 | Reading chips requires recalling red=good + metric + population from other pages; no inline legend. |
| 7 | Flexibility and Efficiency | 2 | No sort, filter, or cross-league aggregate; power user must eyeball 21 chips across 7 cards. |
| 8 | Aesthetic and Minimalist | 3 | Clean but under-designed; ragged desktop whitespace adds noise. |
| 9 | Error Recovery | n/a | No error states (amber limbo tag is honest status, not error). |
| 10 | Help and Documentation | n/a | No help system expected; the missing ramp key is charged under #2/#6. |
| **Total** | | **18 / 28 (64%)** | **Acceptable — functional and honest, hollow at the center.** |

## Design Specificity Verdict

**LLM (Assessment A):** Category-interchangeable — the least-authored surface on the site. Strip the nav chrome and headshots and it's a generic "directory of groups" card grid a CRM, a Pokédex, or a SaaS "teams" page could ship unchanged. The gut-punch: this is the site's **one true geography surface** (7 leagues from Cape Cod to Bismarck to Boca Raton), and DESIGN.md explicitly reserves "maps for geography" as a sanctioned-but-unbuilt encoding — yet there is zero field motif, zero geography, zero signature display. Principles 1 ("the display is the product") and 3 ("the field is the canvas") are both absent. Nothing here would be screenshotted with a "look how good Lewis is" caption; it reads closer to the site's own anti-reference (sterile KPI cards) than to "Savant credibility wearing GT colors."

**Deterministic scan (Assessment B):** `detect.mjs --json site/src/pages/leagues.astro` → `[]`, exit 0 — **clean, 0 findings** (no hardcoded hex, bad easing, or font violations in source). Read narrowly: `.astro` scanning is regex/text mode; the browser-rendered URL mode was unavailable (puppeteer not installed) and exits 0 with `[]` misleadingly, so **rendered contrast, tap-target, and overflow rules never ran**. Those were checked manually (below). No false positives to dispute; the risk here is false-negatives — "clean" means only "no text-level anti-patterns in source."

## Overall Impression

Functional, honest, and quietly on-brand in its parts — but hollow at the center. The single biggest opportunity: this is the geography surface with no geography. It has the strongest claim on the whole site to a "field is the canvas" moment and takes none. Both assessments independently converge on: lead with a map, fix the percentile chips' missing window, and kill the ragged grid.

## What's Working

1. **Integrity is visibly wired in.** Isaiah Galason (CPL) correctly shows the amber "DRAFTED · UNSIGNED · JUL 27" limbo tag and **no** percentile chip; per-league official-site links; a dormant honest-empty-state string for fixture feeds. Lives the "trust to the source / no fake data" principle. (A + B agree; B confirmed the limbo path renders at both viewports.)
2. **Token-driven reuse = same-product feel.** Headshot, PercentileChip, ProvenanceTag, navy/gold nav all shared; the bust headshots are the one humanizing, illustrative touch a plain table wouldn't have.
3. **The per-league row is a legible micro-table.** Portrait + name + summer team + a real number — dense and quiet like a Savant reference row. B measured contrast on all 18 chips at 5.25–6.11:1 — the ≥4.5:1 invariant holds.

## Priority Issues

**[P1] Percentile chips carry no window (metric / population / direction / date).**
- *Why it matters:* Directly contradicts DESIGN.md's own owner flag ("a bare colored percentile chip reads as an overall grade… percentiles carry their window") — the closest thing to a rule violation on the page. A casual fan misreads Tyler Guerin's cold "1" as a verdict on the player; a screen-reader user hears "…Cotuit Kettleers, 30" (context-free number); a colorblind fan can't tell 95 beats 1.
- *Fix:* Caption under the h1 — "Percentile vs. their summer league — OPS (hitters) / ERA (pitchers), through Jul 22. Red = better." Switch to muted/outlined chip authority; add chip aria-labels ("30th percentile OPS vs summer league").
- *Command:* /impeccable clarify

**[P1] No geographic or signature display on the site's geography surface.**
- *Why it matters:* Violates Principles 1 and 3 head-on; the surface with the strongest claim to a signature moment takes none. This is the single biggest specificity unlock.
- *Fix:* Lead with a US map — each league/team a located node sized by GT-player count, colored by performance — cards demoted to a reference layer beneath.
- *Command:* /impeccable overdrive (redesign)

**[P2] Ragged card heights waste the canvas (desktop).**
- *Why it matters:* B measured it: Cape Cod card 571px (10 players) vs. 1-player cards 175–198px; row 2 doesn't start until y=740, leaving a ~366px L-shaped void under the 2-player Appalachian card. Looks unfinished; dilutes the density the product prizes. Root cause: `align-items: start` on an auto-fill grid.
- *Fix:* Masonry (CSS `columns`) so cards pack, or normalize heights.
- *Command:* /impeccable layout

**[P2] No aggregate; the 5-second question is unanswered by any single display.**
- *Why it matters:* Fails Principle 4 ("Five seconds first"). To learn "how are our guys doing?" you must read 7 counts and scan 21 rows. The overview tier of the disclosure ladder is missing.
- *Fix:* A header summary ("N Jackets across 7 leagues") + a small cross-league "hottest right now" score-bug strip (loudest-first, never crowned).
- *Command:* /impeccable overdrive

**[P2/a11y] "Official … site" links are 17px tall — below the 44px tap target.** (B measured.) Player rows are exactly 44px — at threshold, no margin. Small tap targets on mobile.
- *Fix:* Give the official link real height/hit-area; add a touch of vertical padding to rows.
- *Command:* /impeccable adapt

**[P3] No sort/filter; nav/label drift.** DESIGN.md's 1-minute tier promises "filters, league context"; there are none. Nav says "By League", h1 says "Leagues".
- *Fix:* Optional sort + hitter/pitcher toggle; align the label.

## Persona Red Flags

**Alex (power user):** No sort/filter/aggregate — must eyeball 21 chips across 7 cards and decode red=high to find leaders; to answer "top 5 this summer" he leaves for Stats. Bare chip gives a number with no metric.

**Sam (accessibility):** "Color never alone" is satisfied (numbers present) and contrast passes (B: 5.25–6.11:1). But PercentileChip likely exposes only "95" to a screen reader — context-free — and no "red = better" text exists anywhere. Player-row heading order and single-link-per-row model are sound.

**GT diehard, phone, one minute:** Long single-column scroll led by Cape Cod's 10 rows; no "tonight's best" up top, no map, no summary; the freshness stamp he'd want is stuck at the very bottom after the whole scroll. Leaves in under a minute with no screenshot-worthy takeaway.

## Minor Observations

- Nav "By League" ≠ h1 "Leagues" — pick one.
- Chip authority mismatch (solid vs. the muted treatment DESIGN.md assigns summer snapshots).
- The `.sample` fixture empty-state string exists but no league triggers it today — keep as the integrity guardrail, but it's untested in production.
- Official links same weight/color as player links despite leaving the site.
- Team names (Cotuit Kettleers, Bismarck Larks) add context but have no tie to geography a map would give.
- No per-card "stats through" stamp.

## Questions to Consider

1. What if the page LED with a US map — each team a located node sized by GT count, colored by performance — turning the reserved "maps for geography" encoding into the "field is the canvas" moment this surface begs for?
2. What if a cross-league "hottest right now" strip answered "how are our guys doing?" in one display before any card?
3. What if the chip became a proper "summer snapshot" object across the page — muted, captioned, with a "red = better" key — so a first-timer or colorblind fan reads it correctly?
4. What if the reference layer packed as vertical masonry (or one dense, sortable percentile-ranked table) so Cape Cod's 10 rows don't blow out the grid?
