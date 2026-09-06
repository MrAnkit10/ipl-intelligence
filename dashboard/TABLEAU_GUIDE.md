# Tableau Dashboard Build Guide

Tableau Desktop (Apple silicon) 2026.2 is confirmed installed. This guide
gives you every data file pre-computed and ready to connect to with one
click, and the exact worksheets/dashboards to build, mirroring blueprint
section 37 (originally written for Power BI) — same four pages, same
content, Tableau vocabulary.

## About `IPL_Intelligence.twb`

This directory also contains a hand-authored `.twb` (Tableau's XML
workbook format) with one real worksheet (`team_stats.csv` -> a "Team Win
%" bar chart) wired into an "Executive Overview" dashboard. Worth being
precise about what that file actually is:

- Tableau workbooks are normally built through the GUI (drag fields onto
  shelves, arrange visually) — there's no supported API for authoring one
  programmatically. This was written by hand against Tableau's (largely
  undocumented) XML schema.
- It was genuinely tested, not written blind: opened in the real Tableau
  Desktop install on this machine, with Tableau's own log
  (`~/Documents/My Tableau Repository/Logs/log.txt`) read after each
  attempt for its exact DTD validation errors, each one fixed, retested.
  Real bugs were found and fixed this way — an invalid `selection-relaxation-option`
  enum value, a missing `<style/>` element, the required-but-easy-to-miss
  `filter`/`sort`/`perspectives`/`aggregation` sequence inside `<view>`,
  and stale `parent-name` references after a relation rename.
- **What's unverified**: this session's environment has no way to actually
  see a rendered window (screenshots only ever showed the desktop/VS Code,
  never a Tableau window, even once the process was confirmed alive and
  logging a successful render) — so the schema-level errors are confirmed
  fixed, but the CSV data connection currently loads **0 rows** (Tableau's
  log: `"Cell requested for row 0 is out of bounds for table with 0
  rows!"`), for a reason that couldn't be pinned down without visual
  feedback to iterate against. `auto-extract='no'` and the `textscan`
  connection attributes matching a known-working sample were both tried
  without success.

**When you open this file yourself** (on a machine where Tableau can
actually show you a window), you'll be able to see the real error/state
immediately and fix the connection in seconds via the GUI's own "Edit
Connection" dialog — almost certainly faster than continuing to debug it
blind. Treat it as a structurally-valid starting point, not a finished
dashboard. Building fresh via File > New > Text File (the normal path,
described below) is the more reliable route if the existing file gives you
trouble.

## Data Files (all in `data/processed/`)

Regenerate any time with `python -m src.analytics.build_stats_tables`.

| File | Grain | Use for |
|---|---|---|
| `overview_kpis.csv` | 1 row | KPI tiles on the Executive Overview page |
| `matches_bi.csv` | 1 row per match | Season trends, toss analysis (has both original and `canonical_*` team columns — always use the `canonical_*` ones so renamed franchises like RCB Bangalore/Bengaluru aren't split) |
| `team_stats.csv` | 1 row per team | Win %, toss impact, batting-first vs chasing |
| `head_to_head.csv` | 1 row per team pair | Head-to-head records |
| `season_trends.csv` | 1 row per season | Scoring/results trends over time |
| `venue_stats.csv` | 1 row per venue | Venue profiles |
| `batting_stats.csv` / `bowling_stats.csv` | 1 row per player | Player Analytics (already includes `current_team` for filtering) |
| `phase_trends.csv` | 1 row per season × phase | League-wide powerplay/middle/death trends |

For anything needing ball-by-ball detail beyond these, connect directly to
`data/processed/deliveries.parquet` (Tableau 2026.2 reads Parquet
natively — Data > Connect to Data > To a File > Parquet).

## Setup

1. Open Tableau Desktop.
2. Connect to each CSV above as its own data source (Text File connector) —
   don't try to join them into one source; they're at different grains
   (match, team, player, season). Keep them separate and use each on the
   worksheets that need it.
3. Create one Tableau **Dashboard** per page below, combining the
   worksheets listed for that page.

## Page 1 — Executive IPL Overview

**Worksheets:**
- *KPI Tiles*: from `overview_kpis.csv`, one small worksheet per metric
  (Matches Played, Total Runs, Total Wickets, Total Sixes, Total Fours,
  Highest Total, Lowest Total) shown as a big single number (drag the
  measure to Text, set mark type to "Text", enlarge the font).
- *Team Win %*: bar chart from `team_stats.csv` — `team` on Rows,
  `win_pct` on Columns, sorted descending.
- *Season Trends*: dual-axis line chart from `season_trends.csv` —
  `season_year` on Columns, `avg_innings_score` and `chasing_wins_pct` as
  two measures on Rows (combine axes via "Dual Axis").
- *Venue Leaders*: bar chart from `venue_stats.csv` — top venues by
  `matches_played`, colored by `chasing_win_pct`.

**Dashboard filters:** a `season_year` range filter (from `matches_bi.csv`,
applied as a filter action to the other sheets) and a team filter using
`canonical_team1`/`canonical_team2`.

## Page 2 — Player Analytics

**Worksheets:**
- *Top Run Scorers*: bar chart from `batting_stats.csv` — `player_name` on
  Rows (sorted by `runs` descending, limit to top 20 via a Top N filter),
  `runs` on Columns, colored by `current_team`.
- *Top Wicket Takers*: same pattern from `bowling_stats.csv` using
  `wickets`.
- *Batting Career Scatter*: scatter plot from `batting_stats.csv` —
  `strike_rate` on Columns, `batting_average` on Rows, size by `runs`,
  color by `current_team`. This is the single most useful chart on this
  page for spotting anchors vs. finishers.
- *Phase Strike Rate*: bar chart per selected player using
  `strike_rate_powerplay` / `strike_rate_middle` / `strike_rate_death`
  (pivot these three columns into one "phase" field via Tableau's
  **Pivot** transform in the data source, then bar chart phase vs value).

**Dashboard filters:** a single-select `player_name` parameter/filter so
picking one player highlights them across all four worksheets (use a
"Highlight" action, not a "Filter" action, on the scatter plot so context
isn't lost).

## Page 3 — Team Analytics

**Worksheets:**
- *Batting First vs Chasing*: grouped bar chart from `team_stats.csv` —
  `team` on Rows, `win_pct_batting_first` and `win_pct_chasing` as two
  measures.
- *Head-to-Head*: text table (crosstab) from `head_to_head.csv` —
  `team_a` and `team_b` on Rows/Columns, `team_a_win_pct` as the color-coded
  measure. (Optional polish: duplicate the data with `team_a`/`team_b`
  swapped and `team_a_win_pct` recomputed as `100 - team_a_win_pct` via a
  calculated field, so it renders as a full symmetric matrix instead of a
  half-triangle.)
- *Venue Records*: from `venue_stats.csv` — `defending_win_pct` vs
  `chasing_win_pct` per venue, and `most_successful_team`.

## Page 4 — Advanced Analytics

**Worksheets:**
- *League Phase Trends*: from `phase_trends.csv` — `season_year` on
  Columns, `run_rate` on Rows, colored/split by `phase`. A second version
  with `boundary_pct` tells the same story from a different angle.
- *Player Phase Splits*: reuse the pivoted phase table from Page 2, but
  aggregate across all players (drop the player filter) to see league-wide
  phase strike rate distribution as a box plot.
- **Not yet available**: Win Probability Added (player impact) and
  Expected Runs Above Expected are blueprint Version 4 features — no data
  exists for them yet, so don't build placeholder charts for these; add
  them once `src/analytics` has the underlying metric.

## Publishing

`File > Save As` a `.twbx` (packaged workbook, bundles the data) into this
`dashboard/` folder once built, so it lives alongside the rest of the
project and can be committed to git (it's a binary file — check its size
before committing; if it's large, consider Tableau Public's free hosting
and linking to it from the README instead of committing the binary).
