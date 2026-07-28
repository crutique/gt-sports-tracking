-- College baseball dataset -- D1-wide, 2015 onward.
--
-- Lives in schema `cbb` inside the existing `ncaa_baseball` database so the
-- legacy `public.plays` table (2.2M rows, 2021/2022/2023/2026 bands) stays
-- untouched and remains cross-queryable.
--
-- Design notes that are load-bearing:
--
-- * **Everything keeps its receipt.** `cbb.game_source` records which feed a
--   game came from, its URL, when it was fetched and a hash of the bytes. The
--   project rule is that no figure is published without provenance, and that has
--   to be true in the store, not bolted on at render time.
-- * **Names are scored, not canonical.** StatCrew writes whatever the scorer
--   typed -- `Fralick, C.` / `Murphy,Preston` / bare `Vercollone` -- and it
--   varies per school *and per game*. Play rows therefore keep the raw scored
--   name AND a nullable resolved FK, so ingestion never blocks on identity and a
--   later pass can improve resolution without re-fetching anything.
-- * **A zero is a zero.** StatCrew omits attributes that are zero; the loader
--   defaults them, so stat columns are NOT NULL DEFAULT 0. A NULL here would
--   mean "not recorded", which is a different claim.
-- * **Innings are outs.** IP is stored as `ip_outs` (integer) because StatCrew
--   writes innings.outs -- "0.2" is two outs, not two tenths. Storing a float
--   would corrupt every aggregate ERA and WHIP.
-- * **Live and historical share one shape.** `game.status` carries the in-play
--   state so a Gameday view and a 2015 backfill read the same tables.

CREATE SCHEMA IF NOT EXISTS cbb;

-- ---------------------------------------------------------------- reference --
CREATE TABLE IF NOT EXISTS cbb.conference (
    conference_id   serial PRIMARY KEY,
    name            text NOT NULL,
    seo             text UNIQUE,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cbb.school (
    school_id       serial PRIMARY KEY,
    name            text NOT NULL,
    short_name      text,
    -- Normalised match key. Scorers spell the same school many ways ("Texas
    -- A&M" / "Texas A and M" / "Tex. A&M"), so joins go through this rather
    -- than the display name.
    norm_key        text UNIQUE,
    -- external identifiers, each nullable: no single source knows every school
    ncaa_seoname    text UNIQUE,          -- ncaa.com slug, e.g. 'georgia-tech'
    ncaa_team_id    integer,              -- sdataprod teamId
    sb_gid          text,                 -- StatBroadcast gid, e.g. 'geot'
    espn_team_id    integer,
    division        smallint,             -- 1/2/3, null for NAIA & non-NCAA
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS school_sb_gid_idx ON cbb.school (sb_gid);
CREATE INDEX IF NOT EXISTS school_name_idx   ON cbb.school (lower(name));

-- `season` is the SPRING year: 2026 = the 2026 season. NCAA's sdataprod uses the
-- academic start year (2025) and web1.ncaa.org uses the season year directly --
-- both are converted at the edge so nothing downstream has to remember which.
CREATE TABLE IF NOT EXISTS cbb.team_season (
    team_season_id  serial PRIMARY KEY,
    school_id       integer NOT NULL REFERENCES cbb.school(school_id),
    season          smallint NOT NULL,
    conference_id   integer REFERENCES cbb.conference(conference_id),
    wins            smallint,
    losses          smallint,
    conf_wins       smallint,
    conf_losses     smallint,
    UNIQUE (school_id, season)
);
CREATE INDEX IF NOT EXISTS team_season_season_idx ON cbb.team_season (season);

-- ------------------------------------------------------------------ people --
-- One row per human. Cross-season and cross-school identity resolution is a
-- separate, revisable pass -- see `player_season.person_id`.
CREATE TABLE IF NOT EXISTS cbb.person (
    person_id       bigserial PRIMARY KEY,
    full_name       text NOT NULL,
    first_name      text,
    last_name       text,
    bats            char(1),
    throws          char(1),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS person_last_name_idx ON cbb.person (lower(last_name));

CREATE TABLE IF NOT EXISTS cbb.player_season (
    player_season_id bigserial PRIMARY KEY,
    person_id       bigint NOT NULL REFERENCES cbb.person(person_id),
    team_season_id  integer NOT NULL REFERENCES cbb.team_season(team_season_id),
    jersey          text,
    positions       text,                 -- as scored: 'dh/p', 'rf'
    class           text,                 -- FR/SO/JR/SR/GR
    bats            char(1),
    throws          char(1),
    hometown        text,
    last_school     text,
    UNIQUE (person_id, team_season_id)
);
CREATE INDEX IF NOT EXISTS player_season_team_idx ON cbb.player_season (team_season_id);

-- ------------------------------------------------------------------- games --
CREATE TABLE IF NOT EXISTS cbb.game (
    game_id         bigserial PRIMARY KEY,
    season          smallint NOT NULL,
    game_date       date NOT NULL,
    start_time      text,
    home_team_season_id integer REFERENCES cbb.team_season(team_season_id),
    away_team_season_id integer REFERENCES cbb.team_season(team_season_id),
    home_runs       smallint,
    away_runs       smallint,
    innings         smallint,
    neutral_site    boolean NOT NULL DEFAULT false,
    conference_game boolean,
    stadium         text,
    location        text,
    attendance      integer,
    duration        text,
    -- 'scheduled' | 'in_progress' | 'final' | 'postponed' | 'cancelled'
    status          text NOT NULL DEFAULT 'final',
    is_complete     boolean NOT NULL DEFAULT false,
    -- external ids: whichever feeds we have seen this game through
    sb_id           text,                 -- StatBroadcast sbid
    ncaa_contest_id bigint,               -- sdataprod contestId
    espn_event_id   bigint,
    statcrew_gameid text,                 -- <venue gameid>, e.g. 'TX_03'
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS game_sb_id_key   ON cbb.game (sb_id) WHERE sb_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS game_ncaa_id_key ON cbb.game (ncaa_contest_id) WHERE ncaa_contest_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS game_espn_id_key ON cbb.game (espn_event_id) WHERE espn_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS game_date_idx   ON cbb.game (game_date);
CREATE INDEX IF NOT EXISTS game_season_idx ON cbb.game (season);
CREATE INDEX IF NOT EXISTS game_status_idx ON cbb.game (status) WHERE status <> 'final';

-- Provenance. One row per (game, feed) actually fetched.
CREATE TABLE IF NOT EXISTS cbb.game_source (
    game_source_id  bigserial PRIMARY KEY,
    game_id         bigint NOT NULL REFERENCES cbb.game(game_id) ON DELETE CASCADE,
    source          text NOT NULL,        -- 'statbroadcast_xml' | 'ncaa_sdataprod' | 'sidearm_html' | 'presto_html'
    url             text,
    fetched_at      timestamptz NOT NULL DEFAULT now(),
    content_sha256  text,
    byte_length     integer,
    UNIQUE (game_id, source)
);

-- -------------------------------------------------------------- stat lines --
-- NOT NULL DEFAULT 0 throughout: StatCrew omits zero attributes, and the loader
-- fills them. NULL would assert "unknown", which is a different and stronger
-- claim than "did not happen".
CREATE TABLE IF NOT EXISTS cbb.batting_line (
    game_id         bigint NOT NULL REFERENCES cbb.game(game_id) ON DELETE CASCADE,
    player_season_id bigint NOT NULL REFERENCES cbb.player_season(player_season_id),
    batting_order   smallint,
    started         boolean NOT NULL DEFAULT false,
    ab   smallint NOT NULL DEFAULT 0,  r    smallint NOT NULL DEFAULT 0,
    h    smallint NOT NULL DEFAULT 0,  d    smallint NOT NULL DEFAULT 0,
    t    smallint NOT NULL DEFAULT 0,  hr   smallint NOT NULL DEFAULT 0,
    rbi  smallint NOT NULL DEFAULT 0,  bb   smallint NOT NULL DEFAULT 0,
    k    smallint NOT NULL DEFAULT 0,  hbp  smallint NOT NULL DEFAULT 0,
    sf   smallint NOT NULL DEFAULT 0,  sh   smallint NOT NULL DEFAULT 0,
    sb   smallint NOT NULL DEFAULT 0,  cs   smallint NOT NULL DEFAULT 0,
    gdp  smallint NOT NULL DEFAULT 0,  kl   smallint NOT NULL DEFAULT 0,
    PRIMARY KEY (game_id, player_season_id)
);

CREATE TABLE IF NOT EXISTS cbb.pitching_line (
    game_id         bigint NOT NULL REFERENCES cbb.game(game_id) ON DELETE CASCADE,
    player_season_id bigint NOT NULL REFERENCES cbb.player_season(player_season_id),
    ip_outs smallint NOT NULL DEFAULT 0,   -- innings.outs decoded to outs
    h    smallint NOT NULL DEFAULT 0,  r    smallint NOT NULL DEFAULT 0,
    er   smallint NOT NULL DEFAULT 0,  bb   smallint NOT NULL DEFAULT 0,
    k    smallint NOT NULL DEFAULT 0,  hb   smallint NOT NULL DEFAULT 0,
    hr   smallint NOT NULL DEFAULT 0,  bf   smallint NOT NULL DEFAULT 0,
    ab   smallint NOT NULL DEFAULT 0,  sfa  smallint NOT NULL DEFAULT 0,
    sha  smallint NOT NULL DEFAULT 0,  ibb  smallint NOT NULL DEFAULT 0,
    kl   smallint NOT NULL DEFAULT 0,
    pitches smallint NOT NULL DEFAULT 0, strikes smallint NOT NULL DEFAULT 0,
    w    smallint NOT NULL DEFAULT 0,  l    smallint NOT NULL DEFAULT 0,
    sv   smallint NOT NULL DEFAULT 0,  gs   smallint NOT NULL DEFAULT 0,
    PRIMARY KEY (game_id, player_season_id)
);

CREATE TABLE IF NOT EXISTS cbb.fielding_line (
    game_id         bigint NOT NULL REFERENCES cbb.game(game_id) ON DELETE CASCADE,
    player_season_id bigint NOT NULL REFERENCES cbb.player_season(player_season_id),
    po   smallint NOT NULL DEFAULT 0,  a  smallint NOT NULL DEFAULT 0,
    e    smallint NOT NULL DEFAULT 0,
    PRIMARY KEY (game_id, player_season_id)
);

-- ------------------------------------------------------------------- plays --
-- Base-out state is explicit in the source (`outs`, and named runners on
-- first/second/third), so it is stored rather than re-derived. Runner and
-- batter names are kept AS SCORED; the resolved FKs are nullable and filled by a
-- later identity pass.
CREATE TABLE IF NOT EXISTS cbb.play (
    play_id         bigserial PRIMARY KEY,
    game_id         bigint NOT NULL REFERENCES cbb.game(game_id) ON DELETE CASCADE,
    seq             integer NOT NULL,
    inning          smallint NOT NULL,
    half            char(1) NOT NULL,     -- 'V' | 'H' -- the team BATTING
    batting_team_season_id integer REFERENCES cbb.team_season(team_season_id),
    outs_before     smallint,
    runner_first    text,
    runner_second   text,
    runner_third    text,
    batter_name     text,
    batter_hand     char(1),
    pitcher_name    text,
    pitcher_hand    char(1),
    balls           smallint,
    strikes         smallint,
    pitch_sequence  text,                 -- 'KBBSFFS'
    description     text NOT NULL,
    batter_player_season_id  bigint REFERENCES cbb.player_season(player_season_id),
    pitcher_player_season_id bigint REFERENCES cbb.player_season(player_season_id),
    UNIQUE (game_id, seq)
);
CREATE INDEX IF NOT EXISTS play_game_idx    ON cbb.play (game_id);
CREATE INDEX IF NOT EXISTS play_batter_idx  ON cbb.play (batter_player_season_id);
CREATE INDEX IF NOT EXISTS play_pitcher_idx ON cbb.play (pitcher_player_season_id);

-- ------------------------------------------------------- schedule & context --
CREATE TABLE IF NOT EXISTS cbb.ranking (
    ranking_id      bigserial PRIMARY KEY,
    season          smallint NOT NULL,
    as_of           date NOT NULL,
    poll            text NOT NULL,        -- 'rpi' | 'd1baseball' | 'coaches' | 'ncaa'
    team_season_id  integer NOT NULL REFERENCES cbb.team_season(team_season_id),
    rank            smallint NOT NULL,
    value           numeric,              -- RPI/ELO value where the poll has one
    UNIQUE (season, as_of, poll, team_season_id)
);

-- ---------------------------------------------------- movement & acquisition --
CREATE TABLE IF NOT EXISTS cbb.transfer (
    transfer_id     bigserial PRIMARY KEY,
    person_id       bigint REFERENCES cbb.person(person_id),
    player_name     text NOT NULL,        -- as reported, before resolution
    from_school_id  integer REFERENCES cbb.school(school_id),
    to_school_id    integer REFERENCES cbb.school(school_id),
    season          smallint,             -- season they arrive for
    entered_on      date,
    source_url      text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cbb.recruit (
    recruit_id      bigserial PRIMARY KEY,
    person_id       bigint REFERENCES cbb.person(person_id),
    player_name     text NOT NULL,
    to_school_id    integer REFERENCES cbb.school(school_id),
    class_year      smallint,             -- HS graduating class
    position        text,
    hometown        text,
    national_rank   smallint,
    state_rank      smallint,
    source_url      text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cbb.draft_pick (
    draft_pick_id   bigserial PRIMARY KEY,
    person_id       bigint REFERENCES cbb.person(person_id),
    player_name     text NOT NULL,
    draft_year      smallint NOT NULL,
    round           text,
    overall         smallint,
    mlb_team        text,
    from_school_id  integer REFERENCES cbb.school(school_id),
    source_url      text,
    UNIQUE (draft_year, overall)
);

-- ---------------------------------------------------------------- ingestion --
-- Backfill runs for days across ~100k games, so it has to be resumable and has
-- to record what it could NOT get. A missing row here is the gap list.
CREATE TABLE IF NOT EXISTS cbb.ingest_log (
    ingest_id       bigserial PRIMARY KEY,
    source          text NOT NULL,
    key             text NOT NULL,        -- sbid / contestId / url
    season          smallint,
    game_date       date,
    status          text NOT NULL,        -- 'ok' | 'missing' | 'error' | 'skipped'
    detail          text,
    attempted_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, key)
);
CREATE INDEX IF NOT EXISTS ingest_log_status_idx ON cbb.ingest_log (status);
CREATE INDEX IF NOT EXISTS ingest_log_season_idx ON cbb.ingest_log (season);
