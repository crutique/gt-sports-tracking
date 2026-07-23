---
target: draft page
total_score: 16
max_score: 32
na_heuristics: 5,9
p0_count: 1
p1_count: 2
timestamp: 2026-07-23T05-02-30Z
slug: site-src-pages-draft-astro
---
Method: dual-agent (A: isolated design-review subagent · B: isolated detector/browser-evidence subagent)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Live countdown + stamps good; clamped-full pool bar misreports the pool state |
| 2 | Match System / Real World | 2 | "$22M of $21.7M" is an impossible fraction stated as one; "GT 2026" ambiguous; missing slots unexplained |
| 3 | User Control and Freedom | 3 | No traps; receipt links leave the site unsignaled |
| 4 | Consistency and Standards | 1 | Two design generations behind: retired circles, native title tooltip, generic cards, gradient panel, old tag grammar, four date formats |
| 5 | Error Prevention | n/a | No inputs |
| 6 | Recognition Rather Than Recall | 2 | Official-vs-reported only a dotted underline; slot rules unglossed; $500 story buried in prose |
| 7 | Flexibility and Efficiency | 2 | 8 of 9 names dead text; no bridge to /outlook |
| 8 | Aesthetic and Minimalist Design | 2 | 8× "GT 2026", 8× identical Signed chips, notes restating cells; the one varying value is the quietest |
| 9 | Error Recovery | n/a | Static; empty state honest |
| 10 | Help and Documentation | 1 | Zero methodology: slot, official/reported, deadline mechanics |
| **Total** | | **16/32** | **Acceptable-low (50%) — competent skeleton, pre-card-era surface** |

## Design Specificity Verdict

**LLM assessment:** Interchangeable, with one authored idea (the pool band) — and two design generations behind its own site. Next to the outlook's dealt hands and the player page's full card treatment, /draft is a generic white admin table with circle avatars. The one authored element, the pool bar, currently renders as a fully-filled decorative stripe.

**Deterministic scan:** CLI: 1 (the pool card's 3px gold top stripe — deliberate motif, pattern-matched). Runtime (injection verified, live server started and confirmed stopped): 13 findings — 6 × 10px table headers, the 9px "MP" initials, the "Unsigned" chip measured **4.27:1** (under AA — and it's the page's one live status), 11px UDFA subline, the caps deadline label, one padding arguable, font FP, em-dash count (mostly tabular nulls). Mechanical facts that matter more than the rule hits: **the pool bar clamps at 100% while the copy reads "$22M of $21.7M"** — over-commitment is invisible; **this is the only surface on the site still using circle portraits**; mobile hides Slot/Bonus/Status entirely behind a scroller that is not keyboard-focusable (3 focusable descendants total); no table caption; the header date wraps mid-token at 375.

## Overall Impression

The receipt system (reported figures as source links, honest pending states) is the site's integrity principle at its best, and the delta column does the reader's arithmetic. Everything else is a pre-card-era admin table: the money story has no magnitude (the $9.5M→$500 cliff renders in identical numerals), the page's only live tension (Galason, deadline in 4 days) has its lowest visual priority, mobile amputates the answer, and the Jul 27 degrade — after which this page is history forever — doesn't exist. Verdict: card-era rebuild, not polish.

## What's Working

1. **The bonus-cell receipt system** — reported figures link sources, "terms not yet reported" is an honest pending state on a signed deal. No other draft tracker does this.
2. **fmtMoneyDelta inline** ("+$517.4K vs slot") — the one derived number that matters, computed for the reader.
3. **The pool panel's no-JS discipline** — static fallback stays correct; countdown is enhancement only.

## Priority Issues

- **[P0] Mobile amputates the answer.** At 375, Slot/Bonus/Status are off-canvas; visible: pick, name, "Min"/"Athl" slivers. No sticky identity column, no scroll affordance, scroller not keyboard-focusable. The spike audience is on phones.
- **[P1] The deadline degrade doesn't exist — and one path is valence-inverted.** The page never imports isDeadlinePending; and if Galason doesn't sign (the best GT outcome), `did_not_sign` styles **red/bad** — the happiest ending renders as an error. PLAN's archive requirement is unbuilt with four days left.
- **[P1] The page's one live story has its lowest priority.** Galason: the quietest chip, an italic note, two em-dashes. The amber limbo grammar (built, deadline-aware) is unused here; the countdown and its subject sit 400px apart.
- **[P2] The pool bar lies by clamp.** Numerator includes slot-less bonuses; "of" implies a budget GT doesn't hold; at 100% the length encodes nothing — on the site whose rule is that geometry must encode.
- **[P2] Identity drift + measured floors.** Circles → busts; generic card → frame grammar; native title → site tooltip; gradient panel → flat navy; "GT 2026" text → tag grammar; prose notes → label+figure. Plus: 10px headers, 4.27:1 Unsigned chip, 9px initials, 11px subline.
- **[P3] No receipts legend** — one muted line would turn the receipt system from easter egg into visible feature and explain slots/dashes.

## Persona Red Flags

**Alex:** distrusts "$22M of $21.7M" on sight; can't separate official from reported without hovering; "$9.5M" prose beside "$9,497,500" cell; no slot-source statement. **Sam:** class table has no heading or caption (heading nav skips the main content); double name announcements; bare "source" link; pending/unverified links lack aria equivalents. **The diehard ("what did Lackey sign for"):** desktop 3 seconds; phone — not without discovering hidden scroll; Lackey is dead text; nothing worth screenshotting.

## Minor Observations

Mobile date wraps mid-token · row hover implies interactivity on linkless rows · `.delta` re-hardcodes the font stack · the loudest chip style is reserved for a status nobody holds while the live one is quietest · `rel="noopener"` without target — external behavior never decided · UDFA lacks the pending-terms pattern · under-slot red on the biggest bonus in program history reads as failure (money isn't win/loss).

## Redesign Brainstorm

1. **The Draft Class Card Set (M)** — nine gold-framed cards in pick order, the site's exact card grammar: pick corner ("R1 · #3"), bust, team meta, **bonus as the headline numeral carrying its receipt link**, delta beneath, sign-date stamp. Galason's is the visibly un-flipped card. Mobile folds to the sectioned list like the outlook hands. Archival by nature — Jul 28 costs it nothing.
2. **The Money Ladder (S–M)** — one bar per player on a shared linear dollar scale: gold bar = bonus, navy tick = slot. The $9.5M→$500 cliff becomes the picture; Brosius's one-pixel bar makes the senior-sign story tell itself; no tick = no slot (shows the rounds-1–10 rule). Fits 375 natively.
3. **The Limbo Card (S)** — while the deadline pends: an amber-edged strip between pool and class for Galason — bust, "GT signee · R17 · #496 · Washington", the two outcomes as labeled states, **the countdown moved onto it**. After Jul 27 it becomes the resolution card ("Arrived at GT" navy/ok, or the signed figure + receipt).
4. **The Designed Archive Flip (M)** — one component set, two intents switched on isDeadlinePending() at build time: tracker mode (countdown, unsigned emphasis) vs record mode (final ledger line "9 drafted · 8 signed · $22.0M · 1 arrived on campus", role-aware status valence — kills the red-chip inversion).
5. **Segmented Pool (S–M)** — the bar becomes one segment per signed bonus (hover/focus names the player + figure), totals as "$22.0M committed across 8 signings," slot pool as a labeled reference tick beside it. No clamp, no impossible fraction, real per-player encoding.
6. **The Pick Line (S)** — a thin 1→615 number line with gold dots at GT's nine picks (amber for the signee): the class's front-loaded shape in one glance. Timeless post-deadline.

## Questions to Consider

1. This page's data freezes forever in four days — should it be designed primarily as the program's permanent "Class of 2026" artifact, with the countdown as the temporary layer?
2. Whose money is the pool? Would "what did our guys get" (class total, slot as per-player reference) be more honest and more GT than MLB front-office framing?
3. Should the page's center of gravity be the eight who left — or the one who might arrive, the only row connecting this page to next season?
