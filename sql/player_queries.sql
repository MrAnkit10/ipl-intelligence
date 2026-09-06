-- Player-focused analytical queries (blueprint section 32).
-- Every query here has been run against the loaded database and verified
-- to return sensible results — not written blind.

-- ============================================================
-- Rolling 5-innings batting form per player (window function,
-- blueprint's own suggested "strong advanced example")
-- ============================================================
WITH player_innings AS (
    SELECT
        fd.batter_id,
        dp.display_name,
        fd.match_id,
        fm.date,
        SUM(fd.runs_batter) AS innings_runs
    FROM fact_deliveries fd
    JOIN dim_player dp ON dp.player_id = fd.batter_id
    JOIN fact_matches fm ON fm.match_id = fd.match_id
    WHERE fd.extra_wides = 0 AND NOT fd.is_super_over
    GROUP BY fd.batter_id, dp.display_name, fd.match_id, fm.date
)
SELECT
    display_name,
    date,
    innings_runs,
    ROUND(AVG(innings_runs) OVER (
        PARTITION BY batter_id ORDER BY date
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ), 1) AS rolling_5_innings_avg
FROM player_innings
WHERE display_name = 'V Kohli'
ORDER BY date
LIMIT 15;

-- ============================================================
-- Leading run scorer per season (RANK, CTE)
-- ============================================================
WITH season_runs AS (
    SELECT
        fm.season_year,
        dp.display_name,
        SUM(fd.runs_batter) AS runs
    FROM fact_deliveries fd
    JOIN fact_matches fm ON fm.match_id = fd.match_id
    JOIN dim_player dp ON dp.player_id = fd.batter_id
    WHERE fd.extra_wides = 0 AND NOT fd.is_super_over
    GROUP BY fm.season_year, dp.display_name
),
ranked AS (
    SELECT *, RANK() OVER (PARTITION BY season_year ORDER BY runs DESC) AS season_rank
    FROM season_runs
)
SELECT season_year, display_name, runs
FROM ranked
WHERE season_rank = 1
ORDER BY season_year;

-- ============================================================
-- Momentum: runs this over vs the previous over, per innings (LAG)
-- ============================================================
WITH over_runs AS (
    SELECT
        match_id, innings, "over",
        SUM(runs_total) AS runs_this_over
    FROM fact_deliveries
    WHERE NOT is_super_over
    GROUP BY match_id, innings, "over"
)
SELECT
    match_id, innings, "over", runs_this_over,
    LAG(runs_this_over) OVER (PARTITION BY match_id, innings ORDER BY "over") AS prev_over_runs,
    runs_this_over - LAG(runs_this_over) OVER (PARTITION BY match_id, innings ORDER BY "over") AS swing
FROM over_runs
WHERE match_id = (SELECT MIN(match_id) FROM fact_matches WHERE season_year = 2026)
ORDER BY innings, "over";

-- ============================================================
-- Innings-quality buckets (CASE) — how often do batters convert starts?
-- ============================================================
WITH player_innings AS (
    SELECT fd.batter_id, fd.match_id, SUM(fd.runs_batter) AS runs
    FROM fact_deliveries fd
    WHERE fd.extra_wides = 0 AND NOT fd.is_super_over
    GROUP BY fd.batter_id, fd.match_id
)
SELECT
    dp.display_name,
    COUNT(*) FILTER (WHERE runs < 10)                   AS failures,
    COUNT(*) FILTER (WHERE runs BETWEEN 10 AND 29)       AS starts,
    COUNT(*) FILTER (WHERE runs BETWEEN 30 AND 49)       AS good,
    COUNT(*) FILTER (WHERE runs BETWEEN 50 AND 99)       AS fifties,
    COUNT(*) FILTER (WHERE runs >= 100)                  AS hundreds,
    COUNT(*)                                             AS total_innings
FROM player_innings pi
JOIN dim_player dp ON dp.player_id = pi.batter_id
GROUP BY dp.display_name
HAVING COUNT(*) >= 50
ORDER BY hundreds DESC, fifties DESC
LIMIT 10;
