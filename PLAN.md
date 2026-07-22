# GT Summer Tracker — Product Plan

*Authored via product-planner retroactive interview, 2026-07-21. The design-elevator audit ([docs/elevation-plan.md](docs/elevation-plan.md)) is the diagnostic input; this plan supersedes its sequencing where they differ.*

## Concept

GT Summer Tracker is the nightly, trustworthy record of Georgia Tech baseball beyond the college season: how every Yellow Jacket is performing in the summer leagues, and what next spring's roster actually looks like as the draft reshapes it. It must do two things brilliantly: answer **"how are our guys doing?"** in seconds with numbers a baseball-literate fan trusts, and answer **"what is our roster going to look like next season?"** as signings, returns, and arrivals resolve. Its displays — not its prose — are the product: the site should be known for visualizations beautiful enough that GT fans screenshot them into the group chat.

## Audience & core feeling

1. **GT diehards checking daily** — the primary audience; the homepage is theirs.
2. **Draft-curious fans in July** — spike audience; the draft page is theirs.

Feeling in the first 5 seconds: **the trustworthy obsessive** — Baseball Savant credibility that unmistakably feels GT-built. Credible, highly visual and illustrative, data dense. NOT corporate, minimalist, or text-heavy. The screenshot caption to design for is "look how good *Lewis* is" — the site earns "look how good this site is" as a side effect.

## Scope: v1 / later / never

**v1 (this elevation cycle):**
- Everything shipped in Tiers 1–2 (a11y, default sort, mobile rescue, type layer, tokens, sparklines, delta column, quick-jump, league medians).
- The Tier 3 signature set, rebuilt under the approved direction: infield-arc **glance strip** (home), **season narrative** trend with event annotations (player pages), **bonus-pool deadline tracker** (draft).
- **No fake data, ever**: fixture/sample league stats are removed from display and replaced by honest awaiting states. (Hard rule from the interview.)
- **"Last night" recency layer**: what changed in the most recent refresh — movers, debuts, big games — made visible on home.

**v1.5 (next):**
- **Roster Outlook page** — the second core question gets its own surface: next spring's roster as it firms up (returning starters, draft departures, incoming signees, transfers), driven by data that already exists (`gtStatus`, draft status, recruit profiles).
- **Real feeds for the two fixture leagues** (pipeline work; unblocks deleting the sample-data pathway entirely).

**Later:**
- **Geographic map** — players scattered Cape Cod → Bismarck → Boca Raton is a story no table tells; fits the recurring-canvas direction. Needs team geocoordinates in the data.
- **2026 spring (college) season stats** on player pages — "what he did for GT" as context beside "what he's doing this summer." Needs a new pipeline source; design reserves a slot for it in the player hero.
- **Multi-team / multi-school**: theme tokens per school + per-team data directories. Architecture stays static; this is parameterization, not a rewrite.

**Never (for this product):**
- Accounts, comments, or any user-generated content.
- Live in-game data (nightly cadence is the product's honest heartbeat).
- A backend, until a "later" item forces one (none currently do).

## Communication plan (per screen)

| Screen | 5-second question | Deeper questions | Form & why |
|---|---|---|---|
| Home | Who's hot and how good are they really? | What happened last night? Who's moving? | Infield-arc dot strip (position = the comparison encoding) + percentile-sorted table (density = the reference layer) + movers line (annotation = the interface saying what matters) |
| Player | How good is this player's summer, really? | Trend? Big games? Season context? | Savant sliders (kept), rolling-trend chart with event annotations (line = trend encoding), game log (table = reference) |
| Draft | Who signed, for how much, who's coming back? | Money vs. slot? Deadline pressure? | Pool-tracker bar (length = money encoding) + delta column + status chips |
| Leagues | Where are our guys, and how's each group doing? | League context, official links | Cards with median chips; later, the map replaces cards as the primary encoding |
| Roster Outlook (v1.5) | What does next spring look like? | Who's confirmed back? Who's gone? Who arrives? | Diamond-position depth view (the field motif doing IA work) + status-grouped lists |

## Content & data plan

- **Exists, real:** 40 players, nightly pipeline, 18+ game logs, league percentiles with league averages, draft class with sourced bonuses, MLB headshots, recruit profiles.
- **Exists, fake (to remove from display):** CPL + SFCBL fixture stats. Until real feeds land, these leagues show assignment info + awaiting-stats states only.
- **To create:** real CPL/SFCBL ingestion; 2026 spring stats source; team geocoordinates (for the map); per-school theme data (for multi-tenant).

## Technical approach

Static Astro on Vercel, nightly rebuild — unchanged, deliberately. It is the right architecture for a nightly-cadence, no-auth product and scales to multi-team by parameterization (per-school token file, per-team data dir, team-scoped routes). Vitest suite guards the math (contrast ramp, sort, stats, events, pool). WCAG AA is enforced by test, not intention. Fonts are open-license (Barlow Condensed via @fontsource).

## Build sequence

1. **Encode the direction** — /impeccable init; correct its extraction against DESIGN.md; fold the direction into CLAUDE.md (Session 3 of the protocol).
2. **Tier 3 under the direction** — glance strip as the infield arc; narrative trend chart; draft pool tracker. Each ends with screenshot verification + detector pass.
3. **Kill fake data** — fixture-league stats out of every display; awaiting states in.
4. **"Last night" movers layer** on home (uses the events/stats libs already built and tested).
5. **v1.5**: Roster Outlook page; real fixture-league feeds.
6. **Later tier**, in order of story value: map view → 2026 spring stats → multi-team.

## Risks & open questions

- **Fixture-feed timeline** — if CPL/SFCBL real feeds are far off, those leagues' pages stay thin; acceptable under the no-fake-data rule.
- **2026 spring stats source** — not yet identified; the design reserves space but the plan doesn't block on it.
- **Recurring-canvas discipline** — the field motif recurs (approved), but each recurrence must encode real data, never decorate; the anti-patterns list in DESIGN.md enforces this.
- **Draft-deadline shelf life** — the pool tracker's countdown ends July 27; it must degrade gracefully into an archival "how the class signed" display.
