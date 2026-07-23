---
target: individual player pages
total_score: 28
max_score: 36
na_heuristics: 5
p0_count: 1
p1_count: 3
timestamp: 2026-07-23T03-49-07Z
slug: site-src-pages-players-slug-astro
---
Method: dual-agent (A: isolated design-review subagent · B: isolated detector/browser-evidence subagent)

Owner's stated aspiration, weighed throughout: player pages should feel like a baseball card. States reviewed: hitter (Lodise), pitcher (Angelakos), recruit-only (Cole), no-summer-team (Zuckerman), at 1280 and 375.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | "Stats through" strip + honest awaiting states — exemplary |
| 2 | Match System / Real World | 4 | Native baseball vocabulary throughout |
| 3 | User Control and Freedom | 3 | "← All players" runs history.back() from any referrer — label can lie |
| 4 | Consistency and Standards | 3 | The + badge/tooltip vocabulary stops at this page's door; chips still use native title here |
| 5 | Error Prevention | n/a | Static read page, no inputs |
| 6 | Recognition Rather Than Recall | 3 | Hero .761/77 vs trend .615 forces cross-referencing near-twin numerals |
| 7 | Flexibility and Efficiency | 2 | Dead-end leaf: league pill inert, no teammates, no prev/next |
| 8 | Aesthetic and Minimalist Design | 3 | Desktop dead zone below the sliders; KPI tiles echo the brand's own anti-reference |
| 9 | Error Recovery | 3 | Empty states teach — except Zuckerman's, which contradicts his own note |
| 10 | Help and Documentation | 3 | Percentile-population strip is excellent; ramp direction never stated |
| **Total** | | **28/36** | **Good (78%) — branded top, dashboard middle, stub bottom** |

## Design Specificity Verdict

**LLM assessment:** Authored, not interchangeable — but the authorship concentrates in the top 200px. The navy lower-third hero with gold-framed bust and chip is unmistakably this site; the slider panel is a real Savant transposition with lg-avg receipts. Below that: 2×2 white KPI tiles (uncomfortably close to PRODUCT.md's own "sterile KPI cards" anti-reference), a two-column body with a large desktop dead zone, four identical section headers. **Baseball-card distance: far — and the irony is structural.** The site already owns a complete trading-card vocabulary (the outlook hands' 112×176 gold-framed .fcard), and the one page devoted to a single player is the only surface that doesn't use it.

**Deterministic scan:** CLI: 1 finding — the hero's gold top band on rounded corners (the standing brand-motif call; kept deliberately). Runtime detector (injection verified on two pages; live server started and confirmed stopped): **22 findings on the hitter page, 1 on the recruit page** — 11 × undersized text (10px StatGrid labels, 10px "OPS %ile", 10.5px slider bubbles ×6), 8 × measured contrast failures (all one token pair: `--text-mut` #6b7280 on recessed surfaces — 4.3:1 on the info strips, 4.0:1 on the six "lg avg" tick labels), 1 × 11px trend caption, 1 false positive (system font — mandated). Two mechanical facts: raw `#fff` hexes live in StatGrid.astro:63 and PercentileSlider.astro:84,86 (token rule), and the mobile game log's scroll region is keyboard-unreachable with no sticky identity column.

## Overall Impression

The hero delivers the brand promise in five seconds and the integrity plumbing (fixture suppression, receipts, stamps) is the best on the site. But the page is three designs stacked: a broadcast hero, a generic stats dashboard, and — for the players who matter most to 2027 — a stub. The single biggest opportunity is the one the owner named: this page should stop being a dashboard that contains a headshot and become **a card that contains a dashboard**.

## What's Working

1. **The hero band** — navy gradient, gold hatband, gold-framed bust, chip: genuinely GT, zero generic residue.
2. **Slider-panel receipts** — lg-avg ticks, labeled values, and the population strip are honesty most real sports products don't attempt.
3. **Integrity plumbing** — verifiably suppressed fixture stats, teaching empty states, per-figure source links, "stats through" stamps.

## Priority Issues

- **[P0] Zuckerman's empty state contradicts his own note.** "Doesn't have a confirmed summer team yet. Check back soon." renders directly beneath "held out of summer ball for the MLB Draft… expected back at GT." The reigning ACC MVP — the most important 2027 name on the site — gets the emptiest page and a false promise. **Fix:** suppress the speculative branch whenever `note` exists (or set his data status to not_playing).
- **[P1] The signature display shipped as a footnote.** PLAN.md's Tier-3 signature for this page is the season trend narrative; what rendered is a 280×56 sparkline beside up to 600px of dead space. **Fix:** full-width trend band between body and game log — real date axis, event dots annotated with labeled numerals, notes beside.
- **[P1] Mobile hero cram.** At 375 three text columns compete and "CAPE COD BASEBALL LEAGUE" wraps into a three-line gold blob. **Fix:** stack the identity block, context as a strip below, league as nowrap abbreviated text.
- **[P1] Measured floors, contrast, and keyboard debt.** 11 sub-11px labels, 8 real AA misses on one token pair (`--text-mut` over `--line-soft`/`--well`), slider div-soup that never says "percentile" to screen readers, keyboard-unreachable game-log scroller, native-title tooltips. **Fix:** raise floors to 11px, darken the muted-on-recessed pair one step, aria on slider rows, `tabindex="0"` + role/label + edge-fade on the scroller, adopt the site tooltip.
- **[P2] No-stats pages are stubs.** Recruit and no-team pages are a hero plus one sentence — the card-back/year-line moves below give them a real body from data that already exists.
- **[P2] Token strays.** Raw `#fff` in StatGrid and PercentileSlider — the token rule says these route through tokens.

## Persona Red Flags

**Alex (stat-head):** league pill and team are dead text; duplicate 0.77 (season vs rolling-5 at G=5) reads as a bug; no totals row; game log carries no source receipt.
**Sam (screen reader/keyboard):** slider rows announce numbers without ever saying "percentile"; scroller unreachable; gold "i" dots read as bare letters; title-only tooltips invisible.
**GT diehard parent:** shared links show the generic OG image/description, not their kid; nothing on the page is a self-contained object worth screenshotting to the family chat.

## Minor Observations

Twin "i" strips stack on pitcher pages · "2026 SUMMER" floats as an orphan label on no-stats heroes · ERA trend never cues that down is good · `.hot` class name invites a future ramp mistake · back-link label can lie about its destination · the hero bust never receives the + badge — the provenance vocabulary silently ends here · Lodise's UCF-gear portrait is period-accurate card charm, no action needed.

## The Baseball-Card Direction (owner's aspiration — all on-system, no fake data)

1. **The hero card (M)** — rebuild PlayerHero around a scaled-up .fcard (~200×315): the player's actual trading card as a physical object overlapping the navy band — white face, 2px gold frame, portrait anchor, name, pos · class, chip, + badge with provenance tooltip. Navy becomes the table felt. Optional ≤400ms front/back flip only if the back carries content the front doesn't.
2. **Card-back stat block (M)** — replace KPI tiles + dotted list with the classic card back: gold-framed panel, navy name bar, one condensed tabular line — G AB R H 2B 3B HR RBI BB K SB / AVG OBP SLG OPS in Barlow Condensed 600 tabular-nums. Topps-back typography verbatim, existing tokens only. Pitcher variant included.
3. **Year lines (M)** — card backs are one row per season; we honestly have `2026 · Hyannis Harbor Hawks · CCBL` and, for freshmen, `2026 · Etowah HS` + PG grade (currently loose paragraphs). Ship the row structure now; PLAN.md's future 2026-spring-GT stats become the next row. Turns the Cole/Zuckerman stubs into real card backs.
4. **Set stamp (S)** — real cards carry a set mark: "GT SUMMER TRACKER · 2026 SET · CARD 17/42" on the hero card's bottom edge — deterministic, true (the set genuinely has 42 cards), pure label.
5. **Grade corner (S)** — the headline PercentileChip moves onto the card's top-right like a grading-slab label with "OPS %ILE" beneath — the percentile becomes the card's grade, which is how fans already read it.
6. **The teammate hand (M)** — below the game log, deal GT teammates on the same summer team/league as a small hand of the actual 112×176 cards (same fan, same hover-lift), linking onward. Extends the collection metaphor to navigation and fixes the dead-end-leaf problem.

## Questions to Consider

1. Should this page stop being a dashboard that contains a headshot and become a card that contains a dashboard?
2. Sliders, trend, hero — which is the artifact a fan posts to the group chat? That one deserves the full-width slot.
3. When summer stats don't exist, is next spring allowed to be the card front (gtStatus, draft resolution, 2027 position) — or does the page stay summer-only and structurally silent about the players whose whole story is what comes next?
