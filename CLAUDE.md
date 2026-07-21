# GT Summer Tracker

Nightly static tracker of Georgia Tech baseball across the summer leagues (site in `site/`, Astro; data pipeline in `pipeline/`, Python). Two core questions every change must serve: **"how are our guys doing?"** and **"what does next season's roster look like?"**

## Design Context

Authored direction docs — read before any UI work, and treat them as the source of truth over anything inferred from code:

- [PRODUCT.md](PRODUCT.md) — register (product), users, purpose, personality, anti-references, principles.
- [DESIGN.md](DESIGN.md) — the approved "Under the Lights" direction: tokens, type, motion, information design, anti-patterns, taste log.
- [PLAN.md](PLAN.md) — scope (v1 / later / never), per-screen communication plan, build sequence.
- [docs/elevation-plan.md](docs/elevation-plan.md) — the original audit (historical diagnostic; superseded by the three above where they differ).

## Hard rules (non-negotiable, test-enforced where possible)

- **No fake data, ever.** Fixture/sample league stats must never render as stats. Honest awaiting/empty states instead.
- **Contrast is an invariant.** The percentile ramp stays ≥4.5:1 under white text at every value — `site/tests/colors.test.ts` enforces it; change `src/lib/colors.ts` and the test together or not at all.
- **Colors come from tokens.** No new hex values outside `site/src/styles/global.css` (the OG card page is the one sanctioned exception).
- **Motion is state, guarded.** 150ms ease-out cues inside `@media (prefers-reduced-motion: no-preference)`; no entrance choreography or scroll reveals; ≤400ms always.
- **The field motif must encode.** Diamond/arc geometry appears only where it carries real data — never as decoration.
- **Every figure keeps its receipt.** Reported/unverified sourcing links and "stats through" stamps are features, not clutter.

## Working conventions

- Display type is Barlow Condensed (500/600/700 via @fontsource); body/UI stays on the system stack. No third family.
- `npm test` (vitest) and `npm run build` in `site/` must pass before any handoff; lib logic (stats, events, draft math, colors) is developed test-first.
- Verify UI changes in the browser at desktop and 375px mobile before calling them done; the roster table's sticky column, chip placement, and column priority are load-bearing on mobile.
- Regenerate the social card after brand-level changes: `npx playwright screenshot --viewport-size=1200,630 http://localhost:4321/og-card site/public/og.png`.
