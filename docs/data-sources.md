# Data sources — where the stats come from

Plan of record for the data layer. **Rewritten 2026-07-26** after extensive live
probing; supersedes the 2026-07-24 version, whose endpoint guesses and access
assumptions are now known to be wrong in several places.

Today the pipeline scrapes **summer-league box scores** (PrestoSports / iScore) and
the **MLB draft** (statsapi); recruit bio/PG data is hand-curated; **prior-season
college stats + roster bio are hand-backfilled** in `site/src/data/college.json`.
Sections 3–8 cover replacing that hand-backfill with a real college pipeline.

---

## 1. What we need, and why it is hard

Two product questions drive the requirement: *how are our guys doing?* and *what does
next season's roster look like?* Both need per-player **season** lines, and the
Savant-style percentile panel needs the **whole D1 population** to rank against.

The canonical batting line is `G AB R H 2B 3B HR RBI BB K HBP SF SH SB CS`. Most
sources supply the first two-thirds; difficulty concentrates in four fields:

| Field | Needed for | Reality |
|---|---|---|
| **HBP** | OBP, OPS, wOBA, wRC+, PA | absent from most free feeds |
| **SF** | OBP denominator, wOBA, PA | absent from most free feeds |
| **SH** | PA | absent from most free feeds |
| **K (batter)** | K% | present but frequently corrupted |

Without HBP and SF, on-base and every weighted metric derived from it are *wrong*, not
merely imprecise. Project rule: **no gap-filling, no estimation** — a source missing
these cannot be silently patched.

Important nuance: **OBP is recoverable without HBP** when a feed reports it directly
(§3.1), which is why the standard rate slate is in far better shape than the advanced one.

---

## 2. stats.ncaa.org — the canonical source

NCAA's official statistics application; the only free source carrying the **complete**
line for every D1 player.

**Fields** (via `baseballr::ncaa_team_player_stats`):
`AB, H, 2B, 3B, TB, HR, RBI, BB, HBP, SF, SH, K, DP, CS, Picked, SB, RBI2out` +
`BA / OBPct / SlgPct`.

**Endpoints** (corrected — the 2026-07-24 table used stale singular `/team/`, `/player/`
paths; current app uses plural):

```
/teams/{season_team_id}/season_to_date_stats?year_stat_category_id={id}
/teams/{season_team_id}/roster
/team/inst_team_list?sport_code=MBA&division=1
/players/{player_id}
/contests/{id}/{box_score,individual_stats,play_by_play}
/rankings/national_ranking
```

`year_stat_category_id` changes every season — discover it from the page, never
hardcode. Season team ids also differ per season (GT: 2024 `574075`, 2025 `596553`,
2026 `614614`; stable org id `255`).

**No CSV/export endpoint and no API exist.** Historic "Download" links are gone; both
maintained client libraries scrape HTML.

### 2.1 Access status — two independent gates

| Client | IP | Result |
|---|---|---|
| `curl` (any UA/headers) | home | 403 |
| `curl` | cellular (clean) | 403 |
| `curl` | Bright Data ISP proxy | 403 |
| Full browser (real Chrome) | home | 403 |
| Full browser | **cellular (clean)** | **200 — real tables** |
| Full browser | ProtonVPN datacenter | 403 |
| **Headless** Chromium (Playwright) | clean residential `71.56.107.6` | 403 |

1. **Non-browser clients are refused on every IP.** `curl` failed even from the
   cellular address where a browser succeeded — so HTTP-client scraping is not viable
   regardless of network. (This invalidates the 2026-07-24 note suggesting
   `User-Agent: Mozilla/5.0` + sleeps works from residential IPs.)
2. **The household IP `67.191.188.62` is separately deny-listed.** Denial is a
   421-byte static page served identically from all three Akamai edges
   (`184.87.36.188`, `23.47.30.88`, `23.5.145.103`), returned even for `/robots.txt` —
   an IP-reputation refusal, not a bot challenge (a challenge would let the JS sensor run).
3. **Headless Chromium is fingerprinted** and refused even from a clean residential IP.
   Clearing that layer requires anti-detection techniques; `baseballr` does it with a
   stealth `chromote` fallback (issue #410/#411, June 2026).

The deny-list entry was created by ~8 rapid probes on 2026-07-25 and had **not** decayed
after ~16h (re-tested with a full browser; Akamai ref `18.3aec3817.1785084122.9d1abb2f`).
Duration is undocumented and may not be purely time-based.

### 2.2 Rate limits

`baseballr` and `ncaa_stats_py` both enforce **1 request / 5 seconds** with disk
caching, explicitly to avoid IP bans. Assume that floor. A full D1 refresh ≈ 600
requests (~300 teams × batting/pitching) ≈ 50 min.

### 2.3 Ruled out

- **ProtonVPN / Bright Data ISP proxies** — datacenter and proxy ranges refused.
- **Bright Data Web Unlocker** — refuses this domain at the vendor's compliance layer
  (`bad_endpoint … not available for immediate access mode in accordance with robots.txt`).
  Residential proxies additionally require business-email KYC.
- **IPv6** — no IPv6 egress on this connection.
- **Alternate hostnames** — `web1/2/3.ncaa.org` resolve to the same edge but don't serve
  the app (404 on `/teams/...`).
- **Different Akamai edges** — all three return the identical static deny.

### 2.4 Obtaining a clean IP

The cable modem (ARRIS S33) issues exactly **one** DHCP lease. With the Pi on the
modem's second port, link came up at 1000 Mb but DHCP returned no offer
(`IP configuration could not be reserved`). Disconnecting the router and giving the Pi
the primary port **does** yield a separate public address — verified: Pi received
`71.56.107.6`. Cost: the household is offline for the duration.

---

## 3. sdataprod.ncaa.com — NCAA.com's public backend

The GraphQL API behind ncaa.com. **Free, unauthenticated, no bot wall, works from any
network including the banned IP.** This is the live/gameday source.

```
GET https://sdataprod.ncaa.com
  ?meta=<OperationName>
  &extensions={"persistedQuery":{"version":1,"sha256Hash":"<sha>"}}
  &variables=<json>
```

Send `Referer: https://www.ncaa.com/`. **JSON must use compact separators** — the
gateway 500s on the whitespace `json.dumps` emits by default.

| Purpose | Operation | sha256 |
|---|---|---|
| Contests by date | `GetContests_web` | `4bcb5e6432fa9da365c0c19af01b1f9015cc7eb5c21e7af2dba308784a166df7` |
| Box score | `NCAA_GetGamecenterBoxscoreBaseballById_web` | `5e92118b2f424040aa96067aba6d34e882165aaf02e9e73cb9d69317066c6ae8` |
| Play-by-play | `NCAA_GetGamecenterPbpGenericById_web` | `57f922d56d60d88326b62202b3d88e8cd3cfb6687931bc0b5b3dfab089b84faa` |
| Team stats | `NCAA_GetGamecenterTeamStatsBaseballById_web` | `9f790b12845d83075435a1d74724cecbf4af69f4ffe6ccad9c06005ceec2d0cd` |
| Game detail | `GetGamecenterGameById_web` | `26d14df5714c5cd454c9032a1f8ebb1b1dc35173065ab858709b0fa84dd07b5f` |

**Variables**
- contests — `{"sportCode":"MBA","division":1,"seasonYear":2025,"contestDate":"05/15/2026","week":null}`
- box score / pbp — `{"contestId":6548215,"staticTestEnv":null}`

⚠️ **`seasonYear` is the academic start year** — `2025` = the 2026 season. `web1.ncaa.org`
uses the *opposite* convention (§5); never mix them.

**SHAs rotate on frontend releases.** Recover them from any gamecenter page: fetch
`https://www.ncaa.com/game/{id}`, read `<script data-drupal-selector="drupal-settings-json">`
→ `.gamecenter.gqlShas` (24 ops) and `.core.gqlHost`; scoreboard hashes live under
`.scoreboardWidget.shas`. Required variable names surface by sending `variables={}` —
the error names them.

### 3.1 What the box score gives

`data.boxscore.teamBoxscore[].playerStats[]` → `batterStats`, `pitcherStats`,
`fieldStats`, `hittingSeason`. **All players, no leaderboard cap.**

**Key finding — `hittingSeason` is cumulative season-to-date.** A season line is
therefore `max()` across a player's games, never a sum (summing produced 114 HR for a
23-HR hitter). The max is exact and immune to games missing from the schedule scan.
Verified against NCAA's published leaderboards: **AB/H/BB exact 6/6 GT players, HR 3/3.**

Caveats:
- Only ~5% of rows carry cumulative figures; the rest repeat the game line. So each stat
  is `max(cumulative_max, sum_of_game_lines)`.
- `hittingSeason.strikeouts` is **never** populated.
- `boxscore.teams[].teamId` is a **string**, `teamBoxscore[].teamId` an **int**.
- Contradicts the 2026-07-24 note claiming "no G": appearances are countable, and SB is
  the genuinely absent counting stat.

### 3.2 What it cannot give

- **HBP / SF / SH absent from the projection.** Persisted queries can't be extended.
- **Batter K corrupted.** Pitcher lines bleed into the batter column: of 569 "batter"
  strikeouts across GT's season, 514 came from the 213 rows carrying *both* batter and
  pitcher stats. Real position players summed to 55 vs ~430 actual; Advincula read 0
  across 60 games vs 16 official.

**Net:** exact for AB, H, BB, R, RBI, 2B, 3B, HR **and OBP** → AVG/OBP/SLG/OPS/ISO are
exact league-wide. K%, BB% (needs PA), wOBA and wRC+ are not obtainable from this source alone.

### 3.3 Play-by-play

`data.playbyplay.periods[].playbyplayStats[].plays[].playText` — narrative text
containing every event, including the three missing fields.

Grammar, derived from **1,822 real plays across 24 games**:

- Clauses split on `;` **and on a literal `3a`** — the separator (0x3a) arrives with its
  escape prefix stripped: `"FORD, H. singled to left field (1-2 BFK)3a CHAPMAN, R. advanced to second."`
- Trailing `(1-2 KFB)` is the count + pitch sequence, never content.
- HBP is always `"<name> hit by pitch"`.
- **SF appears three ways:** `", SF, RBI"`, `", sacrifice fly, RBI"`, and leading
  `"<name> sacrifice fly to left center putout by lf, RBI"`. An RBI fly out is **not** an
  SF unless the feed marks it.
- Scorer software differs per school *and per game*: `Fralick, C.` / `Murphy,Preston` /
  `Davis Hanson` / `Z. Williams` / bare `Vercollone`.

**Coverage limitation:** PBP missing for 18 of GT's 62 games in 2026 (~29%), ~17% D1-wide.
Those games have full box scores but `periods: 0`. PBP-derived HBP/SF/SH therefore
systematically undercount and must be reported incomplete, never published as totals.

Pre-2026 contest ids (4913884, 5194376, 5291598, 5386534) return **nothing**, while 2026
ids resolve normally; the old ids also 404 on `ncaa.com/game/{id}` — a different id space,
most likely stats.ncaa.org contest ids.

---

## 4. ncaa.com leaderboards — official, exact, capped

Server-rendered HTML, no bot wall, works from the banned IP.

```
https://www.ncaa.com/stats/baseball/d1/current/individual/{cat}[/p2|/p3]
https://www.ncaa.com/stats/baseball/d1/{year}/individual/{cat}     # historical
https://www.ncaa.com/stats/baseball/d1/current/team/{cat}
```

**Category ids:** OBP **504**, HBP **499**, SF **502**, SacBunt 497, BA 200, Hits 483,
2B 488, 3B 490, HR 470, BB 495, R 485, RBI 487, SB 492, TB 494, SLG 321,
"Toughest to Strike Out" 339 (yields batter K), ERA 205, WHIP 596, HitBatters 592.
Full list in the `<select>` on `/stats/baseball/d1`.

**Category 504 is the valuable one** — one page with
`Rank | Name | Team | Cl | Pos | G | AB | H | BB | HBP | SF | SH | PCT`: every wOBA
denominator component together.

**Coverage:**
- **Team boards complete** — 304 rows = all 304 D1 teams, uncapped. Sufficient for exact
  league constants (lgwOBA, wOBA scale, FIP constant).
- **Individual boards value-thresholded** — HBP ~165 rows, SF ~276, BA ~251, BB ~162,
  OBP 150. Top of each distribution (includes all six validated GT hitters), not the
  ~5,000-player population.

---

## 5. web1.ncaa.org — NCAA's legacy stats server

Akamai-fronted but **not deny-listed** — serves the banned IP normally. The deny-list is
per-property.

```
GET  https://web1.ncaa.org/stats/StatsSrv/rankings?sportCode=MBA&academicYear=2026
POST https://web1.ncaa.org/stats/StatsSrv/rankings
     sportCode=MBA&academicYear=2026&rptType=CSV&doWhat=showrankings
     &div=1&rptWeeks=<id>&statSeq=<cat>
```

- `rptType`: **HTML / TXT / CSV / PDF** (PDF posts to `/stats/StatsSrv/pdf/rankings`).
- Newest `rptWeeks` id = `div1val[0]` in the form page JS (2026 D1 = `111`,
  "Through Games 06/22/2026(Final)").
- ⚠️ `academicYear` is the **season year directly** — opposite of sdataprod.
- `statSeq=-103` = "All Statistics" → one ~451 KB CSV with **39 category leaderboards**.

Covers every year including current, updated weekly in-season. **Same cap as §4** —
leaders only (~150–320 rows/category). Team routes (`teamStats`, `selectTeam`, `roster`)
error or require NCAA Membership Login.

---

## 6. Other sources evaluated

| Source | Complete? | HBP/SF/SH | Verdict |
|---|---|---|---|
| **The Baseball Cube** | 300+ schools, 2002→ | ✅ + batter K, IBB, GDP, draft, MLBAM ids | **Validated exact on 6/6 GT players, every field.** Free pages `/content/stats_college/{year}~{schoolid}/` (GT = `20124`); $44 CSV for 5 seasons. Completed seasons only. `curl` 403s; renders in a browser. |
| **FanGraphs college** (College Splits data) | 5,330 batters / 308 teams, minPA=1 | ✅ + precomputed wOBA/wRC+ | Genuinely complete. Policy prohibits programmatic access; sanctioned route is ~$25/yr membership with one-click export, manual once per season. |
| **Baseball-Reference Register** | complete, all conferences | ✅ PA/HBP/SF/SH/GIDP | Free, automatable (`/register/team.cgi?id=5ce5f0f3` = GT 2026; tables wrapped in HTML comments; `Crawl-delay: 3`). ToS discourages scraping — a licensing question. |
| **Conference sites** (Sidearm) | 22 conferences | ✅ | `https://<host>/stats.aspx?path=baseball&year=2026`, no WAF. **Qualifiers only** — 12 GT hitters vs 19 who batted. SEC 404s, Big Ten is an SPA. Cross-check, not primary. |
| **School athletics sites** | per-team | ✅ (season books) | SIDs post end-of-season PDFs (ramblinwreck `wp-content/uploads/2026/06/GT-Baseball-Stats-2026.pdf`) and roster bio. SIDEARM exposes roster JSON at `/api/v2/Rosters/bySport/baseball` (B/T in `custom1`/`custom2`). This is what filled `college.json`. Honest and open, but 300 sites for full D1. |
| **ESPN** (`sports.core.api.espn.com`) | 437 teams | — | Open, but college athlete data stale/malformed: GT's "roster" is 116 all-time entries with duplicate `(H)`/`(P)` records, no current players. Rejected. |
| **Highlightly** | NCAA D1 | HBP ✅, K ✅, **SF/SH undocumented** | Free 100/day, $7.99/mo. Per-player-id lookups under quota (~5,000 requests for a pool). Appears ESPN-derived. |
| **D1Baseball** | full D1 | HBP ✅, K ✅, **no SF/SH** | $139.99/yr, website only, no API. ToS names a $500 excessive-use fee and forbids republishing derived figures. |
| **Commercial vendors** | — | — | Rolling Insights, MySportsFeeds, TheRundown, SportsDataIO, Stats Perform, API-Sports, EntitySport, BetsAPI: **no college baseball at any price**. Sportradar has it but omits HBP/SF/SH. |
| **boydsworld / Massey / WarrenNolan** | — | — | Game results, RPI/SOS only. Zero player data. |
| **collegebaseballdata.com** | — | — | GoDaddy "Launching Soon" placeholder; `api.` subdomain NXDOMAIN. |

**Structural reason for the scarcity:** Genius Sports holds NCAA's data rights through
2032 and runs NCAA LiveStats; its official-data API **excludes baseball**, and baseball
LiveStats slipped to **2027**. There is no official NCAA statistics API, bulk download,
or licensing program. The official feed is enterprise-locked, so everyone affordable is
scraping.

**Client libraries:** `baseballr` v2.0.0 actively maintained, fixed Akamai June 2026 via
stealth `chromote`; its raw `httr2` path returns the same 421-byte 403 as `curl`.
`ncaa_stats_py` last pushed 2025-12-05, bare `requests.get`, no browser fallback — will
not clear current protections.

---

## 7. Recruits (incoming HS) — Perfect Game

`perfectgame.org/Players/Playerprofile.aspx?ID={id}` — national/state/position rankings,
commitments, showcase metrics, grades. **No API; ToS-sensitive.** Keep **hand-curating**
recruit entries; do not auto-scrape.

---

## 8. Local asset — the `ncaa_baseball` database

Recovered from the Pi (2026-07-26). PostgreSQL 15, 871 MB, one table `plays`,
**2,266,344 rows**.

```
play_id, game_id, inning, inning_half, sequence_number,
batting_school_id, fielding_school_id, raw_description,
batter_id, pitcher_id, event_type, hit_location,
rbi_count, runs_scored_on_play, outs_on_play
```

`batting_school_id` populated on 97.3% of rows; 355 distinct schools.

| Band | Games | Season | HBP | SF | SH | K | Identified by |
|---|---|---|---|---|---|---|---|
| 1 | 7,613 | **2021** | 16,972 | 6,222 | 5,177 | 120,987 | Waddell, Malloy, Parada |
| 2 | 8,830 | **2022** | 21,152 | 7,477 | 5,560 | 141,422 | Parada's final year |
| 3 | 1,225 | 2023 | 3,342 | 1,069 | 703 | 21,042 | Rubenstein, Giesler, Dispigna |
| 8 | 4,105 | **2026** | 11,938 | 3,334 | 1,850 | 65,155 | Burress, Advincula, Lackey, Kerce |

A full D1 season is ~8,000–9,000 games, so **2021 and 2022 are essentially complete
league-wide seasons carrying all four scarce fields**, 305–313 schools each.

`event_type` is pre-classified, and `pipeline/ncaa_pbp.py`'s `leading_name()` extracted
the batter from **400/400 sampled descriptions (100%)** across all four event types. So
per-player HBP/SF/SH/K are derivable for the seasons covered.

Note: band 8 stores `Last,First`; older bands store surname only — different scoring
eras, which matters for cross-season player matching.

---

## 9. ⚠️ 2026 is a low-confidence stats year league-wide

StatCrew's XML license expired July 2025 and LiveStats didn't ship, so 2026 D1 schools
split across three incompatible scoring tools (PrestoStats ~54%, StatBroadcast ~23%,
backdated StatCrew ~23%). Documented league-wide symptoms: miscalculated ERAs, pitchers
out of order in box scores, games re-entered after the fact.

This also explains the sdataprod defects in §3.2 — blank names, pitcher/batter stat
bleed, inconsistent cumulative lines. **2026 deserves a caveat in sourcing stamps;
2024–2025 are more trustworthy.** Render honest "awaiting"/partial states where data is
missing, per the no-fake-data rule, and never surface backend detail in audience copy.

---

## 10. Implementation status

**Built and tested** (244 pipeline tests passing, committed `c5bb54d`):

| Module | Role |
|---|---|
| `pipeline/ncaa_api.py` | sdataprod client — persisted queries, permanent disk cache, 5s throttle, `discover_shas()` for hash rotation |
| `pipeline/ncaa_season.py` | season aggregation, cumulative-max logic, surname identity resolution, `pbpGames`/`eventsComplete` completeness reporting |
| `pipeline/ncaa_pbp.py` | PBP event parser (HBP/SF/SH) + roster matching |
| `pipeline/ncaa_backfill.py` | team and pool orchestration |
| `pipeline/college_metrics.py` | wOBA, wRC+, FIP, ERA+, ISO with pool-derived constants |
| `pipeline/college.py` | D1-only Savant-style percentile bundle |

**Blocked on data, not code:** the D1-wide percentile pool. A last-5-games sampling
shortcut proved invalid — only **29 of 150** leaderboard players came out exact, because
cumulative rows are too sparse to catch in a tail sample. A correct pool needs every game
of a season (~18,000 box scores, cacheable, one-time) and still wouldn't yield HBP/SF/SH/K.

**Open questions worth testing:**

1. Do the 2026 games missing from the local database differ from the games where the feed
   lacks PBP? If so, merging the two sources gives better 2026 coverage than either alone.
2. Can the 2021/2022 database seasons anchor a validated wOBA/wRC+ implementation, even
   while current-season percentiles remain pending?
3. Do the ncaa.com leaderboards (§4) plus team totals suffice for a *qualified-player*
   percentile pool, accepting that it excludes low-PA players?

---

## Appendix — identifiers

```
GT org id (stats.ncaa.org)     255
GT season_team_id 2024/25/26   574075 / 596553 / 614614
GT teamId (sdataprod)          42924         seoname: georgia-tech
GT schoolid (Baseball Cube)    20124
GT team id (ESPN)              77
GT id (Baseball-Reference)     5ce5f0f3
Household public IP (banned)   67.191.188.62
```
