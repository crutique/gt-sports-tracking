# Product

## Register

product

## Platform

web

## Users

GT sports fans following Georgia Tech baseball. Primary: GT diehards who check daily through the summer — their context is a phone or a second monitor, a minute at a time, wanting last night and the season picture at a glance. Secondary: draft-curious fans who spike in July to see how departing Jackets and incoming signees fared in the MLB Draft. (Players' families and recruiting-adjacent lurkers are welcome bycatch, not design targets.)

## Product Purpose

The nightly, trustworthy record of Georgia Tech baseball beyond the college season: how every Yellow Jacket is performing across the summer leagues, and what next spring's roster will look like as the draft resolves. Success is threefold: GT fan community adoption (screenshots of its displays circulating in fan spaces), a portfolio-grade piece of work, and a learning vehicle for its builder.

## Positioning

The only place that tracks the entire GT roster's summer — every league, every night, percentile-ranked — with numbers a baseball-literate fan can trust to the source.

## Brand Personality

The trustworthy obsessive: Baseball Savant credibility that genuinely feels GT-built. Credible, highly visual and illustrative, data dense. Warm the way a good broadcast crew is warm — through fluency and enthusiasm for the players, never through decoration. The screenshot caption to earn is "look how good Lewis is."

## Anti-references

- FanGraphs' visual register — adjacent in content, explicitly disliked in look.
- Corporate dashboard minimalism — sterile KPI cards, gray-on-white restraint.
- Text-heavy sports blogging — walls of prose where a display should carry the story.
- Fake-data placeholder culture — sample stats presented as real, under any banner.

## Design Principles

1. **The display is the product** — every screen leads with a visualization worth screenshotting; prose annotates, never carries.
2. **Trust to the source** — every number is real, sourced, and time-stamped; no fake data, ever; uncertainty is labeled, not hidden.
3. **The field is the canvas** — baseball's own geometry (diamond, arc, positions) does information-architecture work; it must always encode real data, never decorate.
4. **Five seconds first** — the primary question ("how are our guys doing?") is answered before any interaction; depth is disclosure, not homework.
5. **Built to travel** — the architecture (tokens, data directories, routes) stays parameterizable for other teams and schools without a rewrite.

## Accessibility & Inclusion

WCAG AA as a tested invariant, not an aspiration: the percentile ramp keeps ≥4.5:1 under white text at every value (enforced in `site/tests/colors.test.ts`); muted text stays ≥4.5:1 on its surfaces. Full keyboard operability including table sorting; visible focus rings on every surface (navy-on-light, gold-on-navy). Color never carries meaning alone — numbers always accompany the ramp. All motion sits behind `prefers-reduced-motion: no-preference` with instant-state fallbacks.
