---
target: players statistics display
total_score: 35
p0_count: 0
p1_count: 2
timestamp: 2026-07-22T23-25-27Z
slug: site-src-components-rostertable-astro
---
# Re-critique — Player statistics display (RosterTable.astro)

Method: dual-agent, fresh contexts. Score 35/40 (was 30). P0 0 · P1 2.

## Movement
Error recovery 1→4 (best-in-class empty states, cross-tab switch preserving query); User control 3→4 (tri-state reset, clear filters); Help 2→3 (footnote). All round-one priority issues confirmed resolved by a blind reviewer; target files scan clean at source.

## New priority issues
- [P1] Scrollable .panel keyboard-inaccessible (no tabindex/role on overflow region) — WCAG 2.1.1 vs PRODUCT.md invariant.
- [P1] No "stats through <date>" provenance stamp on the card — DESIGN.md promises it; screenshots strip context.
- [P2] Sub-threshold chips full volume (1.2-IP red 95 identical to earned 87) — outlined/desaturated .subq variant.
- [P2] Mobile hides denominators (G/AB) — append "· N AB" to team sub-line on phones.
- [P2] tfoot 11.5px at ~175ch (detector) — 12px + capped measure.
- [P3] tabs/panels aria-labelledby; default sort leaks into URLs; placeholder "player or team"; touch sort affordance.

## Adjacent-surface backlog (detector)
LastNight .sl labels 9.5px (146 raw); FieldDiagram .sname 10px.

## Open design question
Within-league percentile default makes OPS non-monotonic — lead confidently or section by league.
