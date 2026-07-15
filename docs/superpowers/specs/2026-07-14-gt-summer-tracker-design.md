# GT Summer Tracker — Design Spec

**Date:** 2026-07-14
**Status:** Approved pending user review

## Summary

A public website for Georgia Tech baseball fans that tracks every player expected on the 2027 GT roster through their 2026 collegiate summer league season. The centerpiece is a Baseball Savant-style player profile: season stats, per-game logs, and percentile sliders showing how the player ranks **within their own summer league**. Data refreshes automatically every night from official league statistics sources.

This supersedes the earlier plan whose deliverable was a CSV; the scraping strategy from that plan (player → team → league → official stats source) carries forward as the data pipeline.

## Goals

- One profile page per tracked player: headshot, season stats, league percentile sliders, game log.
- Percentiles computed against all players in that player's league, clearly labeled as such.
- Roster dashboard listing all tracked players with sortable stats.
- League summary page showing where GT players are spread across leagues.
- Fully automatic nightly refresh; zero manual work during the season.
- Repeatable for future summers (new leagues = new config, mostly).

## Non-goals (v1)

Explicitly discussed and deferred or declined:

- Trend/rolling charts over time (declined for v1; nightly history snapshots are stored anyway so this can be added later).
- GT-only leaderboards (declined for v1).
- "Hot right now" featured strip on the home page (declined with home layout Option A).
- Qualified-player percentile thresholds (user chose all-players comparison pool).
- Auth, comments, or any user accounts.

## Decisions log

| Decision | Choice |
|---|---|
| Audience | Public — GT fan community |
| Refresh cadence | Automatic nightly (GitHub Actions cron, ~4am ET) |
| Percentile pool | **Everyone in the league** with any stats (no PA/IP qualifier); sample-size context shown via PA/IP on profiles |
| V1 pages | Roster dashboard `/`, player profiles `/players/[slug]`, league summary `/leagues` |
| Architecture | Static site rebuilt nightly (Option A) — Python pipeline → JSON in repo → Astro build → Vercel |
| Frontend | Astro, light theme, GT navy `#003057` / tech gold `#B3A369` |
| Profile layout | Split two-column (mockup Option B, refined v2) |
| Season stats block | Hybrid: rate-stat grid + counting-stat dotted list (mockup v4) |
| Hitter sliders | OPS, AVG, OBP, SLG, K%, BB% |
| Pitcher sliders | ERA, WHIP, K%, BB%, HR/9, OPP AVG |
| Home page | Sortable roster table with Hitters/Pitchers tabs (mockup Option A) |

Mockups referenced above are preserved in `.superpowers/brainstorm/40018-1784064440/content/` (not committed; visual reference only).

## Site design

### Page: Roster dashboard `/`

- Nav bar: "GT SUMMER TRACKER" wordmark (navy bar, gold accent), links: Players, Leagues, About (About can be a footer blurb in v1).
- Tabs: **Hitters | Pitchers**. Filter chip: league (All Leagues ▾). Optional filter: GT status.
- One sortable table (FanGraphs-density). Columns:
  - Hitters: headshot, Player, Team · League, G, AB, AVG, OBP, SLG, OPS, HR, RBI, SB, OPS percentile chip.
  - Pitchers: headshot, Player, Team · League, G, GS, IP, ERA, WHIP, K, BB, SV, ERA percentile chip.
- Percentile chips use the slider color scale (blue→gray→red).
- Rows link to player profiles.
- Below the table: a quiet section listing players with `unassigned` or `not_playing` summer status so nobody silently disappears.
- Table sorting/filtering is the site's one JavaScript island; everything else is static HTML.

### Page: Player profile `/players/[slug]`

Approved layout (mockup `profile-layout-v2` + stats block `v4-hybrid`):

1. **Hero header** — navy gradient, gold top accent line. Left: circular headshot with gold ring. Center: name, position · GT status (small caps gold), team name, league as a gold pill badge. Right: season context (e.g., "2026 Summer · 32 G · 118 AB" / IP for pitchers).
2. **League context strip** — light gray band: "ⓘ Percentiles rank {first name} against all {League} {hitters|pitchers}, 2026 season · updated nightly". This plus the header badge plus the percentile section title are the three reinforcing signals of the comparison pool.
3. **Two-column body** (stacks on mobile):
   - Left — **Season Stats**: rate-stat grid of 4 cells (hitters: AVG, OBP, SLG, OPS with OPS highlighted navy/gold; pitchers: ERA highlighted, WHIP, K/9, BB/9), then counting stats as a two-column dotted-leader list (hitters: Games, Hits, Doubles, Triples, HR, RBI | At Bats, Runs, Walks, Strikeouts, HBP, SB/CS combined; pitchers: G, GS, IP, W–L, SV, HLD if available | H, R, ER, BB, K, HB, HR allowed).
   - Right — **{League} Percentiles**: six Savant-style sliders. Each row: metric label, track with gradient fill, percentile bubble (colored, white ring), value at right, and a subtle gray tick on the track with a tiny label beneath marking the league average (e.g., "lg avg .742").
4. **Game log** — full-width table, newest first. Hitters: Date, Opponent, AB, R, H, 2B, 3B, HR, RBI, BB, K, SB. Pitchers: Date, Opponent, IP, H, R, ER, BB, K, HR, W/L/SV decision.

Two-way players get both hitting and pitching blocks stacked.

### Page: League summary `/leagues`

One card per league with GT players: league name + logo-free wordmark, official site link, count of GT players, and the list of those players (headshot thumbnails, linked to profiles). Sorted by player count descending.

### Visual language

- Light theme. Navy `#003057` (headers, emphasis), gold `#B3A369` (accents, badges, section underlines), background `#f6f7f9`, cards white with soft shadows.
- Percentile color scale: continuous blue `#4a7de0` (0th) → gray → red `#d93025` (100th), always oriented so red = good. Same scale for sliders, chips, and any future use.
- Headshots everywhere a player is named: hero (72px), table rows (22px), league cards.

## Architecture

```
pipeline/                    # Python 3.12, managed with uv or pip-tools
  players.yaml               # hand-curated player registry (see schema)
  leagues.yaml               # per-league config: platform, URLs, season ids
  scrapers/
    base.py                  # scraper interface + shared HTTP/session/retry
    pointstreak.py           # one module per stats PLATFORM (not per league)
    prestosports.py
    ...
  percentiles.py             # distributions, league averages, percentile ranks
  validate.py                # pre-publish sanity gate
  build_data.py              # orchestrator: scrape → compute → validate → write
  fetch_photos.py            # one-time/occasional headshot fetcher
  tests/
    fixtures/                # saved HTML/JSON pages per platform
site/                        # Astro + TypeScript
  src/data/                  # pipeline output (committed JSON)
  src/pages/                 # index, players/[slug], leagues
  src/components/            # PercentileSlider, StatGrid, GameLogTable, RosterTable...
  public/headshots/
data/history/YYYY-MM-DD/     # nightly snapshots (committed)
docs/superpowers/specs/      # this document
.github/workflows/nightly.yml
```

### Player registry (`players.yaml`)

Hand-curated by design: discovering a player's summer team is research (roster announcements, team sites), not nightly automation. Schema per player:

```yaml
- name: Jackson Blakely
  slug: jackson-blakely
  gt_status: returning          # returning | transfer | freshman
  position: RHP
  player_type: pitcher          # hitter | pitcher | two_way
  summer:
    status: assigned            # assigned | unassigned | not_playing
    team: Willmar Stingers
    league: northwoods          # key into leagues.yaml
    stats_id: "12345"           # player id/URL slug on the league stats platform
  photo: headshots/jackson-blakely.jpg
```

Known assignments at spec time (verified in prior research): Jackson Blakely, Jamie Vicens, Riley Hasenstab → Willmar Stingers (Northwoods League); Caden Spivey → Trenton Thunder (MLB Draft League). All other tracked players start `unassigned` pending the research pass (see Bootstrap).

Excluded entirely (drafted/signed or transferred out per the original plan): Brosius, Patel, Lackey, Burress, Advincula, Kerce, McKee (likely), Neises, Brown, Dee, Stephenson, Wilcox.

### Scrapers

- One module per **stats platform**; a league is a config entry (platform + base URL + season id). Adding a league on a known platform costs a YAML block, not code.
- Interface: `fetch_league_stats(league_cfg) -> LeagueStats` (full batting + pitching tables for every player in the league) and `fetch_game_log(league_cfg, player) -> list[GameLine]`.
- Prefer JSON/API endpoints discovered via network inspection; fall back to HTML parsing (BeautifulSoup/lxml); Playwright only if a platform is JS-only.
- Polite scraping: single session per league, retries with backoff, ~1 req/sec throttle, honest User-Agent. Nightly volume is small (~20 league-table requests + ~40 game-log requests across all leagues).

### League coverage tiers

Full league tables are NOT assumed to be accessible for every league. Each league is assigned a tier during bootstrap, and the site degrades gracefully:

- **Tier 1 — full league tables retrievable** (expected for the major platforms: Pointstreak, PrestoSports, MLB-affiliated): complete experience — stats, game logs, percentile sliders with league-average ticks.
- **Tier 2 — player stats retrievable, full league tables not practical** (login-gated GameChanger leagues, leaders-only views): profile shows season stats and game log; the sliders section is replaced by a quiet note — "{League} does not publish full league statistics, so percentiles aren't available." Dashboard percentile chip shows "—".
- **Tier 3 — no machine-readable stats**: player appears with team/league and a link to the official site; stats marked unavailable.

Percentiles are computed only for Tier 1 leagues; the UI never shows a percentile built from a partial pool.

### Percentile engine

- **Pool:** all players in the league with nonzero PA (hitters) / nonzero IP or BF (pitchers). No qualification threshold (user decision).
- **Rank:** midrank percentile — percent of pool strictly below the value plus half the ties — rounded to integer 0–99.
- **Orientation:** always higher-percentile = better. Metrics where lower raw value is better (hitter K%; pitcher ERA, WHIP, BB%, HR/9, OPP AVG) are rank-inverted before display.
- **League average (tick mark):** computed from league aggregate totals (e.g., league OPS from summed league counting stats), not the mean of individual player rates.
- **Derived inputs** when a platform's tables omit them: PA ≈ AB + BB + HBP + SF + SH; BF ≈ 3·IP + H + BB (+ HBP if available); hitter K% = K/PA, BB% = BB/PA; pitcher K% = K/BF, BB% = BB/BF; HR/9 = 9·HR/IP; OPP AVG preferred from platform, else H / (BF − BB − HBP − estimated sacrifices). Derivations are flagged in the data (`derived: true`) for transparency.

### Data model (pipeline output)

- `site/src/data/players.json` — array of player records:

```jsonc
{
  "slug": "ryan-zuckerman",
  "name": "Ryan Zuckerman",
  "gtStatus": "returning",
  "position": "INF",
  "playerType": "hitter",
  "summer": { "status": "assigned", "team": "...", "leagueKey": "coastal_plain" },
  "photo": "/headshots/ryan-zuckerman.jpg",
  "asOf": "2026-07-14",                  // per-player staleness stamp
  "hitting": {
    "counting": { "g": 32, "ab": 118, "r": 27, "h": 35, "d": 8, "t": 1, "hr": 6,
                   "rbi": 24, "bb": 15, "k": 28, "hbp": 4, "sb": 9, "cs": 2 },
    "rates":    { "avg": 0.298, "obp": 0.371, "slg": 0.541, "ops": 0.912,
                   "kPct": 0.24, "bbPct": 0.11 },
    "sliders": [ { "metric": "ops", "value": 0.912, "percentile": 87,
                    "leagueAvg": 0.742, "leagueAvgPercentile": 48, "derived": false }, ... ]
  }
}
```

- `site/src/data/gamelogs/{slug}.json` — per-player game array.
- `site/src/data/leagues.json` — per league: key, name, abbrev, officialUrl, platform, tier, gtPlayers[]. (League averages are NOT duplicated here — the per-metric `leagueAvg` each profile needs ships inside that player's `sliders`; decision recorded during Task 8 review.)
- `data/history/YYYY-MM-DD/` — copy of the three outputs above per night.

### Nightly workflow (`.github/workflows/nightly.yml`)

1. Cron ~08:00 UTC (4am ET; all leagues' games long finished).
2. `python pipeline/build_data.py` — scrape leagues independently → compute percentiles → validate → write JSON + history snapshot.
3. Commit data changes; push. Vercel builds and deploys the Astro site on push. **Workflow-authoring note (from Task 9 review):** `build_data.py` exits 1 on a partial failure even though it wrote carried-forward outputs first — the commit/push step must run regardless of that exit code (`if: always()` or equivalent), otherwise one broken league would block deploying every healthy league's fresh data.
4. Also triggerable manually (`workflow_dispatch`) for on-demand refresh.

## Error handling & data quality

- **Per-league isolation:** each league scrapes in its own try/except. A failure logs loudly, keeps that league's previous JSON (players keep their `asOf` stamp, profiles show "updated {date}"), and never blocks other leagues or the deploy.
- **Validation gate before publish (`validate.py`):** rates within sane bounds (0 ≤ AVG/OBP ≤ 1, ERA ≥ 0), league tables non-empty, counting stats never decrease vs. yesterday for the same player, every assigned player found in their league table. Violation ⇒ that league falls back to previous data and the run is marked failed-partial in the Actions log.
- **Missing player:** an assigned player absent from league tables (roster cut, name mismatch) surfaces in the log summary rather than 404ing — profile renders with "no stats recorded yet".
- **Unassigned players:** rendered in the dashboard's "No summer assignment yet" section; profile shows status instead of empty stats.

## Testing

- **Scrapers:** pytest against committed fixture files (real captured pages per platform); no live HTTP in tests. One live smoke-test script run manually when onboarding a league.
- **Percentile engine:** unit tests with small hand-computed distributions, including tie handling, inverted metrics, and derived PA/BF paths.
- **Validation gate:** unit tests for each rule.
- **Site:** Astro build in CI on every push (broken data ⇒ failed build ⇒ no deploy); component-level snapshot of PercentileSlider math (percent → position/color).

## Handoff conditions (recorded during Plan 1 final review)

1. **Sample data must never deploy publicly unflagged.** The committed northwoods data is fabricated sample data attributed to three real players (Blakely, Vicens, Hasenstab). Plan 2's site must treat `platform == "fixture"` in leagues.json as "show a 'sample data — not live stats' disclaimer," and the public launch is gated on Plan 3's real scraper replacing the fixture source. Consider adding an explicit `source`/`provisional` field to players.json.
2. **Fixture→real cutover needs a one-time reset.** The first real scrape will be validated against the committed fabricated `previous` — real counting stats lower than invented ones would trip the decrease check and lock the league on stale sample data via carry-forward. At cutover, delete the committed sample `site/src/data` contents (and optionally the sample history snapshots) before the first real run.
3. **Real scrapers (Plan 3): skip gamelog writes when a present player's log fetch returns empty** — an empty fetch currently overwrites a good log file; only omitted players are protected.

## Bootstrap (pre-launch research, not code)

1. Research pass over all tracked players: find summer team via roster announcements/team sites; fill `players.yaml`; flag unverifiable players for user confirmation.
2. Identify each league's stats platform; verify whether full batting/pitching tables are actually retrievable and assign the league a coverage tier (see League coverage tiers); capture fixture pages; note JSON endpoints.
3. Fetch headshots: GT roster page for returning players; previous school/team sites for transfers and freshmen; store locally in `site/public/headshots/` (a generic silhouette placeholder for anyone missing).
4. Seed `leagues.yaml` for every league that has ≥1 GT player.

## Tracked players

Returning pitchers: Caden Spivey, Brett Barfield, Kayden Campbell, Carson Ballard, Jake Lankie, Dylan Loy, Caden Gaudette, Justin Shadek, Jackson Blakely, Jamie Vicens, Cooper Underwood, Dimitri Angelakos, Riley Hasenstab, Adam McKelvey.
Returning position players: Ryan Zuckerman, Will Baker, Kent Schmidt, Drew Rogers, Caleb Daniel, Coleman Lewis, Judson Hartwell, Nathanael Coupet.
Incoming transfers: Logan Keilen, Cooper Blauser, Holden Pantier, Eli Stephens, Jackson Morgan, Jordan Lodise, Patrick Walsh, Josh Gunther, Brady Fox, Tyler Guerin, Jayden Stroman.
Incoming freshmen: Deion Cole, Jack Richerson, Ezekiel Lara, Kolby Martin, Ryan Engle, Luke Nitkowski, Reid Gainous, Michael Nottleman, Brett Slymen.

## Future ideas (post-v1 backlog)

Trend charts from history snapshots · GT-only leaderboards · "hot right now" strip · qualified-pool toggle for percentiles · JSON/CSV export endpoint · previous-summers archive.
