# Data sources — where the stats come from

Resolved 2026-07-24; **revised 2026-07-25 after live probes** (see §0). This is
the plan of record for the data layer. Today the pipeline scrapes **summer-league
box scores** (PrestoSports / iScore) and the **MLB draft** (statsapi); recruit
bio/PG data is hand-curated; **prior-season college stats + roster bio are
hand-backfilled in `site/src/data/college.json`** from official school sources.

## 0. What live probes established (2026-07-25)

- **`sdataprod.ncaa.com` — NCAA's own GraphQL API — is wide open.** No Akamai, no
  auth; plain GET with persisted-query hashes. Powers ncaa.com. Gives scoreboard,
  schedule, and box scores whose `hittingSeason` blocks carry cumulative season
  AB/R/H/2B/3B/HR/BB/K/AVG/OBP — but **no G, no SB**, so it can't fill the card
  spec alone. Superb as a **cross-check** (verified GT's book to the digit) and
  for game discovery. Reference client: the NCAA Baseball App repo,
  `backend/app/pipeline/scraper/ncaa_graphql.py` (hashes + `seasonYear = calendar − 1`).
- **`stats.ncaa.org` is now hard-blocked**: 403 to plain requests, `curl_cffi`
  chrome-impersonation, and Playwright (headless *and* headed, with the stealth
  flags that worked in March 2026) — from residential IPs (Mac + Pi) as well as
  datacenter. Akamai tightened. We do not escalate into deeper bot evasion.
- **School athletics sites are the honest, open path for per-team needs.** SIDs
  post end-of-season stat books (e.g. ramblinwreck
  `wp-content/uploads/2026/06/GT-Baseball-Stats-2026.pdf`, and
  `2025/06/GT-Baseball-Overall-Stats-2025.pdf`) and roster bio pages (B/T,
  hometown, Last School) that plain-fetch fine. SIDEARM sites also expose a
  roster JSON at `/api/v2/Rosters/bySport/baseball` (B/T hides in `custom1`/`custom2`).
  This filled every card: GT books for returning players, each transfer's prior
  school for theirs.

## TL;DR

- **Per-player / per-team (our card + profile needs): school sites + GraphQL
  cross-check.** Hand-backfill once per season into `college.json`; college stats
  are static outside the spring.
- **All-D1 / historical / play-by-play ambitions: blocked at stats.ncaa.org for
  now.** Revisit via bulk dumps (sportsdataverse parquet, 2021-23 already public),
  henrygd/ncaa-api for live scoreboards, or the 2027 Genius feed — not via bot
  evasion.
- **2026 is a degraded season at the source** (see §3). Render honest "awaiting"
  states where data is missing — consistent with the no-fake-data rule. Never
  surface backend plans in audience copy.

## 1. Foundation — stats.ncaa.org

No official API; a stable, community-reverse-engineered HTML/JSON request pattern.
Endpoints (verified against `baseballr` docs + `collegebaseball` source):

| Data | Endpoint |
|---|---|
| Team season stats | `stats.ncaa.org/team/{school_id}/stats` |
| Player season/career | `stats.ncaa.org/player/index` |
| Player game-by-game log | `stats.ncaa.org/player/game_by_game` (`stats_player_seq=-100` → team log) |
| Roster | `stats.ncaa.org/team/{school_id}/roster/{season_id}` |
| **Box score** | `stats.ncaa.org/contests/{contest_id}/box_score` |
| **Play-by-play** | `stats.ncaa.org/contests/{contest_id}/play_by_play` |
| Scoring summary | `stats.ncaa.org/contests/{contest_id}/scoring_summary` |

`contest_id` comes off the schedule page. **The fiddly part:** `season_id`
(a.k.a. `game_sport_year_ctl_id`) is per-season, and `year_stat_category_id`
(batting/pitching/fielding) **changes every year** — you must keep (year → id)
lookup tables. `baseballr` and `collegebaseball` ship these; reuse them.

**Coverage / history (approximate — probe empirically by walking season_ids back
until 404):** team season stats ~2002→present; box scores / PBP ~2012→present;
player-level season stats patchier by year.

**Access:** Akamai bot protection — plain requests get blocked on cloud IPs;
works with `User-Agent: Mozilla/5.0` + randomized ≤4s sleeps + retries (site is
flaky/times out) **from a residential IP**. No documented rate limit → cache
aggressively, throttle when sweeping all of D1 × many seasons.

## 2. Reference implementations to port (don't start cold)

| Lib | Lang | Value |
|---|---|---|
| **baseballr** (Bill Petti / sportsdataverse) | R | **Canonical** endpoint + ID-lookup map. Actively maintained. Port this logic. |
| collegebaseball (nathanblumenfeld) | Py | Usable starting point (stats, game-by-game, advanced metrics); patch ID tables for recent seasons. |
| CollegeBaseballStatsPackage (CodeMateo15) | Py | Cached **team season stats 2002–2025** + draft; good for historical backfill out-of-the-box. |
| sportsdataverse/baseballr-data | data | Yearly NCAA schedule + PBP dumps. |

No Retrosheet equivalent exists for college — stats.ncaa.org + Boyd's World are
the closest.

## 3. The 2026 ecosystem caveat (important, not our fault)

The college live-stats ecosystem is mid-collapse-and-rebuild: **StatCrew's XML
license expired July 2025**; the official **Genius "NCAA LiveStats" for baseball
slipped to 2027**. In the meantime SIDs are split across PrestoStats (~54%),
StatBroadcast (~23%), and backdated StatCrew (~23%), emitting incompatible formats
with documented data-quality errors. **So 2026 box/game data at the source is
patchy and error-prone.** Season aggregates hold up better than live/box feeds.
Design for it: validate against a second source, render "awaiting"/partial states.

## 4. Play-by-play & live

- **Post-game PBP/box: stats.ncaa.org** (§1) — official, all-D1, receipts-backed.
  Effectively post-game, not a reliable live feed. **Build this first.**
- **Near-live (opportunistic):** a specific school's live-stats widget
  (Sidearm `…/sidearmstats/baseball/summary`, PrestoStats, StatBroadcast
  StatMonitr). Per-vendor, fragile, media-gated in places — best-effort for
  marquee games (e.g. GT), not a blanket promise.
- **henrygd/ncaa-api** (mirrors ncaa.com): clean JSON for **live scoreboard/box**,
  5 req/s, self-host via Docker — a good redundancy source while 2026 is unstable.

## 5. Supplements & cross-checks

- **Boyd's World** — deep historical schedules/results (~1990s+) and RPI inputs.
- **Baseball-Reference college register** — normalized season stats (D1 2011+),
  a clean **manual cross-check**; ToS prohibits scraping.
- **Warren Nolan** — RPI / rankings / SOS each season.
- **School Sidearm/Presto sites** — last resort for one team's richest local box
  score (GT = ramblinwreck.com), or to fill a stats.ncaa.org gap.

## 6. Recruits (incoming HS) — Perfect Game

`perfectgame.org/Players/Playerprofile.aspx?ID={id}` — rankings (national/state/
position), commitments, showcase metrics, grades. **No API; ToS-sensitive.**
Keep **hand-curating** recruit entries (matches current posture); don't auto-scrape.

## 7. Commercial (only when scale/revenue justifies)

- **College Splits** — what **FanGraphs** uses; supplies MLB clubs; derived
  stats/splits, D1 back to 2021. Licensed/B2B.
- **Sportradar Global Baseball v2** — lists NCAA baseball; turnkey real-time; paid.
- **Genius Sports** — official NCAA partner; **baseball LiveStats targets 2027.**
  Design ingestion so we can swap to it (or a redistributor) when it ships.

## 8. What the competition uses

- **FanGraphs (college):** College Splits (confirmed).
- **D1Baseball:** live product on a "Batter Box Sports" platform (upstream
  unconfirmed); paywalled/Cloudflare to us.
- **Diamond** (Crossover Sports, 2026): 300+ teams, live/box/PBP + **in-house
  advanced metrics** (wOBA, wRC+, FIP…). Core stats source undisclosed; confirmed
  only a D1Baseball scouting partnership + Statcast for select tournament games.
  Best inference: **scrape NCAA + school feeds, compute metrics in-house** — which
  matches the creator's own "not paying an aggregator, figuring it out."

## Phased plan

1. **v1 (build on the Pi):** port `baseballr`'s NCAA logic to Python; GT first
   (`school_id` for Georgia Tech), pull season stats + game logs + box scores;
   normalize into the same shape as the summer data; nightly, cached, residential
   IP. This backfills the card's "previous college stats" block **and** is step 1
   of all-D1/history.
2. **v1.5:** widen to all D1 (per-(team, season) jobs off the ID lookup tables);
   backfill history as far as endpoints resolve.
3. **v2 (if it's worth it):** license College Splits (clean derived stats) or
   Sportradar (real-time). Watch 2027 Genius for the official feed.

## Confidence & gaps

- **High:** stats.ncaa.org is authoritative/all-D1/scrapable; endpoint patterns
  above; Akamai protection; the 2026 StatCrew→Genius outage; baseballr is the best
  reference; FanGraphs = College Splits.
- **Verify before committing code:** exact earliest box-score/PBP year (probe);
  current `year_stat_category_id` values for 2024–2026 (packages drift); the live
  JSON schema behind Sidearm/Presto/StatBroadcast (inspect a live game's Network
  tab). Any specific app's private contracts are unknowable — don't assume.
