# GT Summer Tracker — Art Direction

*Direction A, "Under the Lights," approved 2026-07-21 after specimen review (A vs. dossier vs. scoreboard). Tuning from contrast pairs: navy carries heroes and signature displays only; the field-as-canvas motif recurs across surfaces; no grafts from the losing directions. This document is the authored source of truth — extraction tools (`/impeccable init`) describe what IS and are corrected against this, never the reverse.*

## Direction statement

Savant credibility wearing GT colors under stadium light. Navy heroes and illustrative, field-shaped data displays make the site unmistakably Georgia Tech's; dense white reference tables keep it unmistakably trustworthy. Numbers arrive like a broadcast score-bug — instantly, then get out of the way.

## References & extracted principles

- **baseballsavant.mlb.com** — one encoding system (blue-cold → red-hot) carried identically on every surface; percentile position as the universal comparison; credibility through density + restraint. *Extracted: the ramp is a language, not a decoration.*
- **mlb.com/gameday** — the field itself as the data canvas; diagrammatic baseball. *Extracted: geometry of the game does IA work (approved as a recurring motif).*
- **ramblinwreck.com** — GT's own voice: heavy condensed all-caps navy display, gold as band/accent, white field. *Extracted: the type register that reads "genuinely GT" (we fix their gold-on-gold contrast sins).*
- **ESPN (score bugs / broadcast graphics)** — state changes announced in ~150ms cues; information appears already-composed, never assembling itself. *Extracted: motion as state, zero choreography.*
- **NYT The Upshot (sports graphics)** — the annotation layer: graphics that say what matters (leaders, change, context) instead of only showing data. *Extracted: every signature display states its takeaway.*

## What we transpose

**Keep (quality DNA):** Savant's ramp-as-language and percentile idiom; Gameday's field-as-canvas; GT's condensed-caps navy/gold register; broadcast-fast state motion.
**Deliberately change:** typeface family (Barlow Condensed, not GT's licensed faces or Savant's system voice); the ramp's anchor colors (ours are AA-safe under white text, enforced by test); the field rendered as a flat illustration (muted grass/dirt tones, clean white lines — MLB-app style; no textures, no photorealism) used only where position is the encoding; gold restricted to identity + emphasis (never a text-bearing background at body sizes).

## Typography system

- **Display: Barlow Condensed** (500/600/700, @fontsource, OFL). All-caps for page headlines, hero names, section energy; sentence case allowed in annotations. Letter-spacing +0.01em at display sizes; never below −0.02em. Scoreboard numerals (stat cells, trend values) use 600.
- **Body/UI: the native system stack** — argued for, per product register: 12.5–15px data-dense tables render best on native rendering, cost zero bytes, and keep the display layer's contrast high. Identity lives in the display layer, not the body.
- **No third family.** (The dossier's mono-citation voice was considered and declined — receipts stay in the body face, muted.)
- Scale: 34–36px h1 · 26px scoreboard numerals · 15/14px body · 12.5px table · 11px floor for labels (10px only for uppercase table headers). `tabular-nums` on all stat cells.

## Color system

Tokens live in `site/src/styles/global.css`; the ramp's anchors mirror `site/src/lib/colors.ts` and are contrast-tested in `tests/colors.test.ts` (≥4.5:1 under white text at every percentile — a hard invariant).

- **Dominant: GT navy** `#003057` (+ `--navy-dark #00223f`, `--navy-bright #00406f`) — carries heroes and signature displays only; body surfaces are `--bg #f6f7f9` / `--card #fff`.
- **Identity accent: Tech gold** `#b3a369` (+ light `#d9c98f`, deep `#8f8250`) — borders, brand marks, player dots, section rules. Never body-text-on-gold.
- **Data ramp:** `#3566cc` (cold) → `#5f6d83` → `#c53022` (hot); red = good, Savant convention.
- **Status:** ok `#e2efe4/#1e5b2a` · warn `#fdf3dd/#92600a` · bad `#f3e9e9/#7a3535` · up/down `#1e5b2a`/`#a33430`.
- **Neutral ramp:** `#f6f7f9 → #eef1f5 → #e6eaef → #dde3ea → #6b7280 → #111827`; on-navy text `#fff / #cfd8e3 / #a9bfd1`.
- **Banned:** purple-gradient defaults; cream/parchment body; any new hex outside the token file.

## Spacing & grid

- Base unit 4px; committed steps **4 / 8 / 12 / 16 / 24 / 32**; 1040px content wrap.
- Density is a feature: tables run tight (10px 8px cells), prose caps at 65ch, whitespace spends itself on the signature displays, not between table rows.
- Cards only as data containers (tables, panels); never nested; full-bleed tables keep 14px first/last-column inset.

## Motion character

- **Personality: the score-bug.** 150ms, `cubic-bezier(0.22, 1, 0.36, 1)`, state-conveying only (hover, sort, tab, filter). No entrance choreography, no scroll-triggered reveals — content is already there.
- **Signature moment:** the glance strip's dots may draw along the arc once on load (≤400ms, ease-out), enhancing an already-visible default.
- **Reduced motion:** every transition wrapped in `@media (prefers-reduced-motion: no-preference)`; the reduced experience is instant state, never a broken one.

## Information design

- **Encodings:** position/length for comparison (sliders, pool bar); lines for trends (sparklines, narrative chart); the ramp as reinforcement, never the sole channel (numbers always present); maps for geography (later tier); **the field's geometry used literally** — players placed at their positions on a diagrammatic ballpark (the Roster Outlook field). The field is a *positional* canvas, not an abstract axis: the percentile-arc experiment was rejected (dots off the ring read as noise; bending a 1D axis into an arc served the motif, not the data). Each field use must encode real data; motif-as-decoration is banned.
- **Disclosure:** 5s (glance strip + sorted table) → 1min (movers, filters, league context) → 5min (player deep-dives, draft money). Overview first, filter, details on demand.
- **Annotation layer (numeric, not verbal):** signature displays state their takeaway through marks, chips, and labeled numerals — a leader dot labeled "LEWIS · 96", a stat pill, a highlighted tile — never through generated prose. Labels, not sentences; the longest permitted annotation is a terse label + figure. The nightly refresh is visible (ticker, movers, "stats through" stamps).
- **Integrity (non-negotiable):** no fake data, ever — fixture stats never render; every reported figure links its source; "unverified" stays labeled; empty states say why they're empty.

## Titles & labels

Section titles are plain descriptive nouns: "Player statistics", "Game log", "2027 roster by position", "Last night". Never wordplay, slogans, or broadcast-catchy phrasing ("Every Jacket, Every League" was rejected as corny — confirmed 2026-07-21). The voice of a serious data site: the displays are expressive, the labels are not.

## Component voice

- **Tables** are the reference layer: quiet, dense, sortable, sticky-identity on mobile, percentile chips as the only color.
- **Chips** speak the ramp; **sliders/arcs** are the showpieces — gold dots with navy strokes on neutral tracks.
- **Buttons/controls** are compact and navy-committed when active (filled), well-gray when idle; focus ring navy-on-light, gold-on-navy.
- **Heroes** are broadcast lower-thirds: condensed caps name, gold meta line, context right-aligned.
- Empty states teach ("stats land with the nightly refresh"), never apologize.

## Anti-patterns (this design must never)

- Show placeholder/sample stats as if real (hard interview rule).
- Put body text on gold, or white text on any untested ramp color.
- Use the field motif decoratively (turf textures, stitched-leather skeuomorphism, diamonds that encode nothing).
- Add a third type family, hero-metric gradient cards, side-stripe borders, or gradient text.
- Animate entrances/scroll reveals; exceed 400ms on any motion.
- Lead with text where a display can carry it (the site is "NOT text-heavy") — but every display keeps its numbers visible.
- Generate prose from data (verbal headlines, adjective performance lines). The site never *writes about* the numbers; it stages them. Confirmed correction 2026-07-21: even the hero speaks in headshot + numerals + labels.
- Introduce hexes outside the token file (the detector + tests are the enforcement).

## Taste log

- **Likes (confirmed 2026-07-21):** Savant idiom; MLB Gameday's field-as-visual; condensed athletic caps; navy-dominant heroes with white data surfaces; recurring field canvas; illustrative density; screenshot-worthy displays as the brand.
- **Dislikes (confirmed 2026-07-21):** FanGraphs' look ("presenting similar things" but disliked); corporate/minimalist/text-heavy registers; fake data in any form; the dossier's serif voice and the scoreboard's gold-drenched surfaces (specimen losers — B "too quiet/print," C "too costume"); **generated verbal headlines/adjective lines — the user vetoed prose-led displays mid-build: visuals and stats talk, words are labels**; **"star of the night" editorial crowning — show everyone's night as a scores panel, order by loudness, never crown**; **the percentile arc/"half wheel" — rejected; the ballpark visual means positions (roster on a field), not a bent axis.**
