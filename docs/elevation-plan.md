# GT Summer Tracker — Elevation Plan

*Design-elevator audit (elevate mode), 2026-07-21. Evidence: live capture of gt-sports-tracking.vercel.app at desktop (1600×900) and mobile (375×812) widths — home, Draft, Leagues, and player pages — full source read of `site/src`, and an Impeccable detector run against the live URL.*

## Verdict

This is a **competent, honestly-built product with one genuinely distinctive surface** — the player page, whose Savant-style percentile sliders (with league-average ticks) are already elite-adjacent thinking. The identity (GT navy/gold, gold-ring headshots) is real and consistently applied; the editorial integrity system (sourced bonus figures, "unverified" flags, sample-data banners, careful empty states) is better than most professional sports sites. What holds it at competent: the interface never *says* anything (no annotation layer, no leaders, wrong default sort), the typography has no identity or scale (nothing on any page is larger than 24px, one system font), there is literally zero motion and zero custom hover/focus feedback, and on mobile the primary question — "how are our guys doing?" — is unanswerable without discovering an unaffordanced horizontal scroll. The biggest lever is **communication, not decoration**: pre-sort by the story, add a leaders/annotation layer, and use the game-log data you already collect (18 per-player JSON files, currently rendered only as raw tables) for trend encodings. Realistic ceiling: with Tiers 1–2 this reads like a serious analytics product; with one Tier-3 signature moment it becomes the reference for how a college program's summer should be tracked.

## Impeccable detector findings (evidence)

Run: `npx impeccable detect https://gt-sports-tracking.vercel.app` → 3 anti-patterns:

1. **[cramped-padding]** `div.card`: children flush against background on all sides (no inset) — the roster table card has zero padding; the table header row lands on the card edge.
2. **[line-length]** ~155 chars/line (aim <80) — footer and subtitle text run the full 1040px wrap with no `ch` constraint.
3. **[overused-font]** primary font "helvetica" at 99% of text — the system-font stack means zero typographic identity.

## Where this audit argues with its own tools

- **overused-font**: partially sustained. A system stack for *table numerals* on a stats site is defensible (rendering speed, tabular clarity — FanGraphs ships system faces in tables too). The real gap is narrower than the detector claims: there is no **display layer**. Fix headings and hero numerals; leave table body text native if you like.
- **cramped-padding**: overruled as stated. Full-bleed tables inside cards are the sports-reference convention (Savant, B-Ref); an 8px inset would look worse. The *legitimate* kernel of the finding: the table's first/last cells need horizontal padding that matches the card radius (12–16px on the outer columns), and the mobile clipping makes the flush edge read as broken.
- **line-length**: sustained without argument. `max-width: 65ch` on footer/subtitle prose costs one line of CSS.

## Scorecard

| Area | Grade | Cause |
|---|---|---|
| Typography | **generic→competent** | One system family; page max 24px; hierarchy by weight/microcaps only; no tabular-nums in the roster table; 9–10px labels |
| Color | **competent** | Real navy/gold identity + fit-for-purpose Savant scale, but ~20 ad-hoc hexes outside the 13 tokens, and AA failures (below) |
| Spacing & layout | **competent** | Sound density; no spacing scale (5,6,7,8,9,10,12,14,16,18,20,22,24,26 all appear); card/table edge tension |
| Motion | **generic** | Zero transitions/animations anywhere; tab switch, sort, hover all instant with no feedback |
| Components & states | **competent** | Proper tab ARIA and excellent empty states, but: only hover state on the whole site is link underline; no row hover; no custom focus styles; sort headers mouse-only |
| Content & imagery | **distinctive** | Real headshots with gold-ring treatment, real data, sourced/flagged figures, honest banners; one mangled subtitle |
| Structure & UX | **competent+** | Clean 3-page IA; URL-persisted tab/filter/sort with smart back-link (rare, genuinely good); no search/jump; no recency signal |
| Communication | **competent (split)** | Player-page sliders are elite-adjacent; home/draft/leagues have no annotation layer, unsorted default order buries the story, slot-vs-bonus delta left for the reader to compute, mobile hides all stats |
| Technical | **distinctive** | Static Astro, tested libs (sort/state/colors/format), fast; missing favicon and OG/social meta entirely |

**Accessibility (measured, auto-Tier 1):**
- White text on mid-percentile chips `#8e9bb0` = **2.81:1** (AA needs 4.5:1; 11px bold is not "large text"). Even the blue end `#4a7de0` = 3.96:1. Roughly the 20th–75th percentile range of chips fails.
- "lg avg" tick labels: 9px at **2.89:1** on the page background.
- Sortable `<th>` elements have click handlers but no `tabindex`, no key handler — sorting is mouse-only.
- No `:focus-visible` styles anywhere (grep: zero matches for "focus" in `src/`).

## Benchmarks

- **Baseball Savant** — the sliders already borrow its best idea. What it adds that this site lacks: *one encoding system carried everywhere* (its red/blue means the same thing on every surface; here chips appear on home but game logs and leagues get nothing), and hover-guided dense tables.
- **FanGraphs** — *opinionated defaults*: leaderboards ship pre-sorted by the stat that matters; conditional color in table cells; sticky identity column on mobile scroll.
- **NYT Graphics / The Pudding** — *the annotation layer*: the graphic states its takeaway ("Lewis leads all GT hitters — 96th percentile in the NWL") instead of leaving the reader to mine it.

## Tier 1 — Quick wins (days)

1. **Contrast repair** (measured failures above): darken the percentile ramp ends/midpoint or switch mid-range chips to dark-text-on-light-fill; raise tick labels to ≥11px `#6b7280`. Keep red=good semantics.
2. **Keyboard + focus**: `tabindex="0"` + Enter/Space handler on sortable `th`; a site-wide `:focus-visible` ring (2px gold on navy surfaces, navy on light). One CSS block + ~6 lines JS in `RosterTable.astro`.
3. **Default sort = the story** (FanGraphs): render the home table pre-sorted by OPS %ile desc (set `data-dir` server-side so aria-sort is right on load), and add a subtle ↕ affordance to sortable headers.
4. **Mobile table rescue**: sticky player column (`position: sticky; left: 0` + background) and a right-edge scroll shadow; drop G/AB behind a breakpoint. The primary question must be answerable on a phone without discovering scroll.
5. **Display type layer**: one self-hosted athletic condensed face (e.g. Barlow Condensed or Archivo — two weights) for h1s, hero name, and stat-cell numerals; h1 24→36px, hero name to 32px, `font-variant-numeric: tabular-nums` on all stat cells. Addresses the detector's overused-font finding at the identity layer only.
6. **Draft delta column**: render bonus−slot inline (`+$517K` / `−$211.5K`, green/red) — the story of that page, currently left as reader arithmetic.
7. **Micro-motion with guard**: 150–200ms ease-out on row hover, tab switch, chip hover; wrapped in `@media (prefers-reduced-motion: no-preference)`.
8. **Housekeeping**: `max-width: 65ch` on footer/sub prose (detector line-length); 12–16px outer-column padding in card tables (the defensible kernel of cramped-padding); fix subtitle to "Tracking Georgia Tech's 2027 roster through the 2026 summer leagues"; add favicon + OG title/description/image (this site gets shared in group chats — link previews are currently blank).

## Tier 2 — Structural (weeks)

1. **Tokenize**: spacing scale (4/8/12/16/24/32), neutral ramp, semantic status colors in `global.css`; migrate the ~20 stray hexes (`#e6eaef`, `#5b6472`, `#eef1f5`, `#cfd8e3`, `#fdf3dd`…). Enforce with the Impeccable detector in CI.
2. **Overview layer on home** (NYT principle): a leaders strip above the table — top OPS, top ERA, hottest last-7 (computable from existing game logs) — each a name + number + chip linking to the player.
3. **Trend encodings from data you already have**: 18 gamelog JSONs exist and render only as raw tables. Add a rolling-OPS sparkline to the player page next to the sliders; optionally a tiny last-10 sparkline column in the roster table. This is the single highest leverage-per-effort item in the plan.
4. **Carry one encoding everywhere** (Savant principle): percentile color appears on home chips only. Extend restrained conditional color to game-log key cells and a league-page median-percentile chip per league card.
5. **Quick-jump**: a filter-as-you-type input over 40 players (no framework needed; the names are already in the DOM).
6. **League cards get a number**: each league card shows median GT percentile + combined line, so Leagues answers a question instead of listing links.

## Tier 3 — Signature moments (the ambition gap)

1. **"The Summer, at a glance"** — one annotated strip at the top of home: every GT player as a gold dot positioned on a single 0–100 percentile axis (their league-relative percentile), names on hover, Lewis labeled at 96. The whole program's summer in one glance; no college fan site has this. It is also the correct encoding for the data (position for comparison), which is why it doubles as the communication fix.
2. **Player season narrative**: rolling-OPS line chart annotated with events ("7/17: 2-HR day", "12-game hit streak") generated from gamelog facts — The Pudding's technique on data already in the repo.
3. **Bonus-pool deadline tracker** (timely — deadline July 27): a single stacked bar of signed money vs. remaining slot value with a countdown; becomes the page people check this week, then gracefully becomes an archive.

## What NOT to change

- **The percentile slider component** — league-avg tick included, this is the site's best idea. Extend its encoding elsewhere; don't redesign it.
- **Navy/gold identity and gold-ring headshots** — distinctive, keep.
- **The editorial-integrity system** — reported/unverified source links, sample-data banners, per-status empty states. This is the site's soul; most pro sites don't bother.
- **URL-state persistence + back behavior** — rare craft, keep.
- **Static Astro + the test suite** — right architecture for nightly-refresh data.

## Suggested sequence

1. Tier 1 #1–2 (contrast, keyboard/focus — measured AA failures, auto-first).
2. Tier 1 #3–4 (default sort, mobile rescue — the two cheapest communication fixes; evidence: buried 1.079 OPS on load, clipped stats at 375px).
3. Tier 1 #5–8 in one styling pass (type layer, draft delta, motion, housekeeping — all detector-evidenced or copy-level).
4. Tier 2 #1 (tokens) before any new components, so #2–6 are built on the scale, not beside it.
5. Tier 2 #3 (sparklines) → Tier 2 #2 (leaders strip) — trend data feeds the leaders logic.
6. Tier 3 #1 as the first signature (it reuses the percentile encoding + tokens), then #3 if shipped before July 27, else #2.
