---
target: players statistics display
total_score: 30
p0_count: 0
p1_count: 2
timestamp: 2026-07-22T22-26-52Z
slug: site-src-components-rostertable-astro
---
# Critique — Player statistics display (RosterTable.astro)

Method: dual-agent (A: isolated design-review agent · B: isolated detector/browser-evidence agent)

## Design Health Score (30/40 — Good)
1 Visibility 3 — no result count; silent zero-results · 2 Real world 4 · 3 Control 3 — no reset to default sort · 4 Consistency 3 — numeric first-click sorts ascending · 5 Error prevention 3 — cross-tab search dead end · 6 Recognition 3 — unlabeled mobile chip; hover-only abbr · 7 Flexibility 4 · 8 Aesthetic 4 · 9 Error recovery 1 — zero-result dead air · 10 Help 2 — "OPS %ile" never defined

## Anti-Patterns Verdict
LLM: not slop; authored (server-side sort, key-stat column, chip migration). Generic residue: toolbar strip.
Detector: source scan clean. Rendered page: 10px table headers (below own 11px floor), 9.5px hero scoreline labels (adjacent surface), monogram tiles 4.2:1 (navy-dark on gold-deep) — genuine catch. FPs: ellipsized spans, gold tab underline, helvetica.

## Priority Issues
- [P1] Silent zero-result states (search/league/cross-tab) — add in-table empty row + count + clear-filters. → harden
- [P1] Sort operability invisible to AT (th not announced operable; tablist no arrow keys; bare-number chips). → audit + harden
- [P2] Numeric columns sort ascending first — default desc. → polish
- [P2] No qualifier threshold on percentile rankings (95 chip on 1.2 IP tops Pitchers tab) — trust risk. → harden
- [P2] Monogram tiles 4.2:1; 10px headers below the 11px floor. → polish

## Personas
Alex: ascending-first tax, no count, no sort reset, no / shortcut, q not in URL. Sam: unannounced sort headers, no arrow-key tabs, context-free chips, abbr unreachable, .opt columns vanish from a11y tree. Dana: Pitchers top-row community-note magnet; mobile clips OPS numerals mid-scroll; full roster never fits one viewport.

## Minor
Search matches hidden chip digits; good empty copy not reused for filtered emptiness; no sticky header; two-way player unmarked across tabs.

## Questions
Define the percentile on-surface? Phone version as ranked chip-list? Screenshot-safe state (qualifier + fitting viewport)?
