-- Season aggregation: per-game lines rolled up to player-season and team-season.
--
-- These are the tables the site and any analysis actually read. They are
-- *views*, not copies, so they can never drift from the game rows underneath --
-- a game corrected by a re-ingest is corrected here for free.
--
-- Why the rate stats can be computed honestly here, when the earlier NCAA-JSON
-- path could not: OBP needs HBP and SF, and K% needs batter strikeouts. The JSON
-- feed supplied none of the three (batter K was 0 across 395 real rows in a 2025
-- sample). StatCrew XML carries all of them as explicit fields, so nothing below
-- is estimated or gap-filled.
--
-- Guards: every denominator is wrapped in NULLIF so a player with no at-bats
-- yields NULL rather than a divide-by-zero or a fake .000 -- "no data" and
-- "zero" are different claims and the project rule is not to conflate them.

-- ------------------------------------------------------ player-season batting
CREATE OR REPLACE VIEW cbb.v_player_season_batting AS
SELECT
    ps.player_season_id,
    ps.person_id,
    per.full_name,
    ts.season,
    ts.team_season_id,
    s.school_id,
    s.name  AS school,
    ps.class,
    ps.positions,
    ps.bats,
    ps.throws,
    count(*)                        AS g,
    sum(bl.ab)::int                 AS ab,
    sum(bl.r)::int                  AS r,
    sum(bl.h)::int                  AS h,
    sum(bl.d)::int                  AS d,
    sum(bl.t)::int                  AS t,
    sum(bl.hr)::int                 AS hr,
    sum(bl.rbi)::int                AS rbi,
    sum(bl.bb)::int                 AS bb,
    sum(bl.k)::int                  AS k,
    sum(bl.hbp)::int                AS hbp,
    sum(bl.sf)::int                 AS sf,
    sum(bl.sh)::int                 AS sh,
    sum(bl.sb)::int                 AS sb,
    sum(bl.cs)::int                 AS cs,
    sum(bl.gdp)::int                AS gdp,
    -- total bases: singles are h - (2b + 3b + hr)
    (sum(bl.h) + sum(bl.d) + 2 * sum(bl.t) + 3 * sum(bl.hr))::int AS tb,
    -- plate appearances, exact because SH/SF are real fields here
    (sum(bl.ab) + sum(bl.bb) + sum(bl.hbp) + sum(bl.sf) + sum(bl.sh))::int AS pa,
    round(sum(bl.h)::numeric   / NULLIF(sum(bl.ab), 0), 4) AS avg,
    round((sum(bl.h) + sum(bl.bb) + sum(bl.hbp))::numeric
          / NULLIF(sum(bl.ab) + sum(bl.bb) + sum(bl.hbp) + sum(bl.sf), 0), 4) AS obp,
    round((sum(bl.h) + sum(bl.d) + 2 * sum(bl.t) + 3 * sum(bl.hr))::numeric
          / NULLIF(sum(bl.ab), 0), 4) AS slg,
    round(sum(bl.k)::numeric
          / NULLIF(sum(bl.ab) + sum(bl.bb) + sum(bl.hbp) + sum(bl.sf) + sum(bl.sh), 0), 4) AS k_pct,
    round(sum(bl.bb)::numeric
          / NULLIF(sum(bl.ab) + sum(bl.bb) + sum(bl.hbp) + sum(bl.sf) + sum(bl.sh), 0), 4) AS bb_pct
FROM cbb.batting_line bl
JOIN cbb.player_season ps ON ps.player_season_id = bl.player_season_id
JOIN cbb.person per       ON per.person_id       = ps.person_id
JOIN cbb.team_season ts   ON ts.team_season_id   = ps.team_season_id
JOIN cbb.school s         ON s.school_id         = ts.school_id
GROUP BY ps.player_season_id, ps.person_id, per.full_name, ts.season,
         ts.team_season_id, s.school_id, s.name, ps.class, ps.positions,
         ps.bats, ps.throws;

-- ----------------------------------------------------- player-season pitching
CREATE OR REPLACE VIEW cbb.v_player_season_pitching AS
SELECT
    ps.player_season_id,
    ps.person_id,
    per.full_name,
    ts.season,
    ts.team_season_id,
    s.name  AS school,
    ps.class,
    ps.throws,
    count(*)                        AS app,
    sum(pl.gs)::int                 AS gs,
    sum(pl.ip_outs)::int            AS ip_outs,
    round(sum(pl.ip_outs)::numeric / 3, 1) AS ip,
    sum(pl.h)::int                  AS h,
    sum(pl.r)::int                  AS r,
    sum(pl.er)::int                 AS er,
    sum(pl.bb)::int                 AS bb,
    sum(pl.k)::int                  AS k,
    sum(pl.hb)::int                 AS hb,
    sum(pl.hr)::int                 AS hr,
    sum(pl.bf)::int                 AS bf,
    sum(pl.w)::int                  AS w,
    sum(pl.l)::int                  AS l,
    sum(pl.pitches)::int            AS pitches,
    sum(pl.strikes)::int            AS strikes,
    round(27.0 * sum(pl.er) / NULLIF(sum(pl.ip_outs), 0), 2) AS era,
    round(3.0 * (sum(pl.h) + sum(pl.bb)) / NULLIF(sum(pl.ip_outs), 0), 3) AS whip,
    round(27.0 * sum(pl.k) / NULLIF(sum(pl.ip_outs), 0), 2) AS k9,
    round(sum(pl.k)::numeric / NULLIF(sum(pl.bf), 0), 4) AS k_pct,
    round(sum(pl.bb)::numeric / NULLIF(sum(pl.bf), 0), 4) AS bb_pct
FROM cbb.pitching_line pl
JOIN cbb.player_season ps ON ps.player_season_id = pl.player_season_id
JOIN cbb.person per       ON per.person_id       = ps.person_id
JOIN cbb.team_season ts   ON ts.team_season_id   = ps.team_season_id
JOIN cbb.school s         ON s.school_id         = ts.school_id
GROUP BY ps.player_season_id, ps.person_id, per.full_name, ts.season,
         ts.team_season_id, s.name, ps.class, ps.throws;

-- --------------------------------------------------------------- team-season
CREATE OR REPLACE VIEW cbb.v_team_season_batting AS
SELECT
    ts.team_season_id, ts.season, s.school_id, s.name AS school,
    count(DISTINCT bl.game_id)      AS g,
    sum(bl.ab)::int AS ab, sum(bl.r)::int AS r, sum(bl.h)::int AS h,
    sum(bl.d)::int  AS d,  sum(bl.t)::int AS t, sum(bl.hr)::int AS hr,
    sum(bl.bb)::int AS bb, sum(bl.k)::int AS k, sum(bl.hbp)::int AS hbp,
    sum(bl.sf)::int AS sf, sum(bl.sh)::int AS sh,
    round(sum(bl.h)::numeric / NULLIF(sum(bl.ab), 0), 4) AS avg,
    round((sum(bl.h) + sum(bl.bb) + sum(bl.hbp))::numeric
          / NULLIF(sum(bl.ab) + sum(bl.bb) + sum(bl.hbp) + sum(bl.sf), 0), 4) AS obp
FROM cbb.batting_line bl
JOIN cbb.player_season ps ON ps.player_season_id = bl.player_season_id
JOIN cbb.team_season ts   ON ts.team_season_id   = ps.team_season_id
JOIN cbb.school s         ON s.school_id         = ts.school_id
GROUP BY ts.team_season_id, ts.season, s.school_id, s.name;

-- ------------------------------------------------------------- coverage view
-- What we actually hold, per season. This is the honesty layer: it is what the
-- site should consult before publishing any season figure, and what tells us
-- which seasons are still too thin to rank against.
CREATE OR REPLACE VIEW cbb.v_season_coverage AS
SELECT
    g.season,
    count(*)                                   AS games,
    count(DISTINCT g.home_team_season_id)      AS home_teams,
    min(g.game_date)                           AS first_game,
    max(g.game_date)                           AS last_game,
    sum(CASE WHEN g.is_complete THEN 1 ELSE 0 END)::int AS complete_games,
    (SELECT count(*) FROM cbb.play p
      JOIN cbb.game g2 ON g2.game_id = p.game_id WHERE g2.season = g.season) AS plays
FROM cbb.game g
GROUP BY g.season
ORDER BY g.season DESC;
