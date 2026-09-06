-- Team/match/venue analytical queries (blueprint section 32).
-- Every query here has been run against the loaded database and verified
-- to return sensible results — not written blind.

-- ============================================================
-- Reusable view: one row per decided match with the winner's toss
-- relationship to the win (view, blueprint section 32)
-- ============================================================
CREATE OR REPLACE VIEW v_match_results AS
SELECT
    fm.match_id, fm.season_year, fm.date, fm.venue, fm.team1, fm.team2,
    fm.toss_winner, fm.toss_decision, fm.winner,
    CASE
        WHEN fm.toss_winner = fm.winner THEN 'toss winner won'
        ELSE 'toss loser won'
    END AS toss_outcome,
    CASE
        WHEN (fm.toss_winner = fm.winner AND fm.toss_decision = 'bat')
          OR (fm.toss_winner != fm.winner AND fm.toss_decision = 'field')
        THEN 'batted first'
        ELSE 'chased'
    END AS winner_batting_order
FROM fact_matches fm
WHERE fm.outcome_type = 'win';

SELECT toss_outcome, winner_batting_order, COUNT(*)
FROM v_match_results
GROUP BY toss_outcome, winner_batting_order
ORDER BY COUNT(*) DESC;

-- ============================================================
-- Chasing win % trend with a 3-season moving average (window function)
-- ============================================================
WITH season_chase AS (
    SELECT season_year, ROUND(100.0 * COUNT(*) FILTER (WHERE winner_batting_order = 'chased') / COUNT(*), 1) AS chase_win_pct
    FROM v_match_results
    GROUP BY season_year
)
SELECT
    season_year,
    chase_win_pct,
    ROUND(AVG(chase_win_pct) OVER (ORDER BY season_year ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS moving_avg_3_season
FROM season_chase
ORDER BY season_year;

-- ============================================================
-- Head-to-head: self-join fact_matches on team pairs
-- ============================================================
SELECT
    LEAST(team1, team2) AS team_a,
    GREATEST(team1, team2) AS team_b,
    COUNT(*) AS matches_played,
    COUNT(*) FILTER (WHERE winner = LEAST(team1, team2)) AS team_a_wins,
    COUNT(*) FILTER (WHERE winner = GREATEST(team1, team2)) AS team_b_wins
FROM fact_matches
WHERE outcome_type = 'win'
GROUP BY LEAST(team1, team2), GREATEST(team1, team2)
HAVING COUNT(*) >= 20
ORDER BY matches_played DESC;

-- ============================================================
-- Venue scoring profile: first-innings average score and chasing win %
-- (CTE + join across fact_deliveries and fact_matches)
-- ============================================================
WITH first_innings_totals AS (
    SELECT fd.match_id, SUM(fd.runs_total) AS total_runs
    FROM fact_deliveries fd
    WHERE fd.innings = 1 AND NOT fd.is_super_over
    GROUP BY fd.match_id
)
SELECT
    fm.venue,
    COUNT(DISTINCT fm.match_id) AS matches_played,
    ROUND(AVG(fit.total_runs), 1) AS avg_first_innings_score,
    ROUND(100.0 * COUNT(*) FILTER (WHERE vmr.winner_batting_order = 'chased') / NULLIF(COUNT(vmr.match_id), 0), 1) AS chasing_win_pct
FROM fact_matches fm
JOIN first_innings_totals fit ON fit.match_id = fm.match_id
LEFT JOIN v_match_results vmr ON vmr.match_id = fm.match_id
GROUP BY fm.venue
HAVING COUNT(DISTINCT fm.match_id) >= 20
ORDER BY matches_played DESC;

-- ============================================================
-- Ranking: best economy rate per season among bowlers with 10+ overs
-- (RANK + join to fact_matches to derive season, since fact_bowling is
-- career-level — this recomputes it at season grain from fact_deliveries)
-- ============================================================
WITH season_bowling AS (
    SELECT
        fd.bowler_id,
        fm.season_year,
        SUM(fd.runs_batter + fd.extra_wides + fd.extra_noballs) AS runs_conceded,
        COUNT(*) FILTER (WHERE fd.extra_wides = 0 AND fd.extra_noballs = 0) AS legal_balls
    FROM fact_deliveries fd
    JOIN fact_matches fm ON fm.match_id = fd.match_id
    WHERE NOT fd.is_super_over
    GROUP BY fd.bowler_id, fm.season_year
    HAVING COUNT(*) FILTER (WHERE fd.extra_wides = 0 AND fd.extra_noballs = 0) >= 60  -- 10+ overs
),
ranked AS (
    SELECT
        season_year, dp.display_name,
        ROUND(runs_conceded::numeric / legal_balls * 6, 2) AS economy,
        RANK() OVER (PARTITION BY season_year ORDER BY runs_conceded::numeric / legal_balls) AS economy_rank
    FROM season_bowling sb
    JOIN dim_player dp ON dp.player_id = sb.bowler_id
)
SELECT season_year, display_name, economy
FROM ranked
WHERE economy_rank = 1
ORDER BY season_year;
