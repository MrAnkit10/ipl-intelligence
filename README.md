# IPL Intelligence — Cricket Analytics & Win Prediction Platform

An end-to-end cricket analytics platform built on 19 seasons (2008-2026) of IPL
ball-by-ball data: Python data engineering, PostgreSQL/SQL, descriptive
analytics, a calibrated win-probability model, player analytics, venue
analysis, a batter-vs-bowler matchup engine, and an interactive Streamlit
application.

Status: data foundation, descriptive analytics, a calibrated win-probability
model, a player performance predictor, the Streamlit app, and a working
local PostgreSQL database are all complete. See
[Development Roadmap](#development-roadmap) below.

## Architecture

```
Cricsheet JSON  ->  Python parser  ->  matches / deliveries / players
                                              |
                                              v
                                        PostgreSQL + SQL
                                              |
                          -------------------------------------
                          |                |                  |
                 Descriptive Analytics   Machine Learning   Tableau
                          |                |
                          -------------------------------------
                                              |
                                    Streamlit application
```

## Data Source

[Cricsheet](https://cricsheet.org/downloads/) ball-by-ball JSON for every IPL
match. Raw files are treated as immutable and are not committed to this
repository (see `.gitignore`) — they're regenerated with the scripts below.

## Project Structure

```
ipl-intelligence/
├── data/
│   ├── raw/          # untouched source files (gitignored)
│   ├── processed/    # matches.parquet, deliveries.parquet, players.parquet, stats tables
│   └── features/     # ML-ready feature tables
├── notebooks/         # exploration, EDA, modeling notebooks
├── src/
│   ├── data/          # download, parse, normalize, validate
│   ├── features/      # feature engineering
│   ├── models/         # train / predict / evaluate
│   ├── analytics/      # batting / bowling / team / venue analytics
│   └── database/       # PostgreSQL connection layer
├── sql/                # schema + analytical queries
├── dashboard/          # Tableau build guide
├── scripts/            # environment-fix helper scripts
└── app/                # Streamlit application
```

## Reproducing the Project

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
scripts/fix_macos_libomp.sh                # only needed on macOS without Homebrew

python -m src.data.download_data          # fetch Cricsheet IPL JSON + player register
python -m src.data.parse_cricsheet        # build matches/deliveries/players tables
python -m src.data.validate_data          # sanity-check the parsed tables
python -m src.analytics.build_stats_tables  # batting/bowling/team/venue stats
python -m src.analytics.overview          # tournament headline numbers
python -m src.data.fetch_photos           # player/venue photos from Wikimedia (a few minutes)
python -m src.features.build_features     # win-probability feature table
python -m src.models.train                # train, calibrate, evaluate
python -m src.models.predict              # example live win-probability call

python -m src.features.build_player_performance_features  # player-performance feature table
python -m src.models.train_player_performance              # train, evaluate
python -m src.models.predict_player_performance             # example prediction

streamlit run app/Home.py                 # the full application
```

Current scale: **1,243 matches**, **295,732 deliveries**, **805 players**,
seasons 2008-2026.

## PostgreSQL

No Homebrew on this machine, so Postgres runs via **Postgres.app** instead
(a self-contained `.app` bundle — no `brew install postgresql`, no sudo):

```bash
# one-time setup
export PGBIN="/Applications/Postgres.app/Contents/Versions/17/bin"
"$PGBIN/initdb" -D ~/pgdata -U $(whoami) -A trust --encoding=UTF8
# started via a LaunchAgent (~/Library/LaunchAgents/com.ipl-intelligence.postgres.plist)
# so it's already running and starts automatically on login — no manual start needed.

createdb -h /tmp -p 5432 ipl_intelligence
psql -h /tmp -p 5432 -d ipl_intelligence -f sql/schema.sql
python -m src.database.load_data      # loads dim_/fact_ tables from data/processed/
```

`src/database/db.py` reads `DATABASE_URL` from a local `.env` (gitignored;
see `.env.example`). Query it directly with `psql -h /tmp -p 5432 -d
ipl_intelligence`, or through `sql/player_queries.sql` and
`sql/analytics_queries.sql` — CTEs, window functions (rolling 5-innings
form, `RANK()`, `LAG()`), `FILTER`, and a view, all run against the live
data and verified to return sensible results (blueprint section 32).

## Making XGBoost/LightGBM Work Without Homebrew

Both packages' macOS wheels link against `@rpath/libomp.dylib` and expect
it at `/opt/homebrew/opt/libomp/lib/libomp.dylib` (i.e. they assume
Homebrew) — `pip install` succeeds but `import xgboost` fails at dlopen
time. This machine already has `libomp.dylib` via its Anaconda install, so
`scripts/fix_macos_libomp.sh` repoints each package's compiled extension at
that file directly with `install_name_tool` — no global `DYLD_LIBRARY_PATH`
(which breaks numpy's Accelerate-framework linking if set broadly), no
Homebrew, no sudo. Re-run it after any `pip install --upgrade
xgboost`/`lightgbm`, since reinstalling restores the original path.

## Win Probability Model

`python -m src.features.build_features` builds a ball-by-ball second-innings
feature table (142K balls across 1,234 decided matches). `python -m
src.models.train` does a chronological season split (train <=2022, validate
2023-2024, test >=2025), compares **Logistic Regression, Random Forest,
XGBoost, and LightGBM** (the full progression blueprint section 19 asks
for), calibrates the best one with isotonic regression, and saves it to
`models/win_probability.pkl`.

Validation results (used for model selection):

| Model | Log Loss | ROC-AUC |
|---|---|---|
| Logistic Regression | 0.523 | 0.852 |
| **Random Forest (selected)** | **0.481** | **0.853** |
| XGBoost | 0.509 | 0.854 |
| LightGBM | 0.512 | 0.852 |

XGBoost/LightGBM needed real regularization to be competitive at all — a
first pass with no `subsample`/`colsample_bytree`/`reg_lambda` scored log
loss 0.68 (worse than Random Forest's 0.49), and simply adding more boosting
rounds made it *worse* (up to 1.03), confirming overfitting on the wide,
sparse one-hot-encoded venue/team feature space rather than undertraining.
Regularized settings closed most of the gap (see comments in
`src/models/train.py`), but Random Forest still wins here without a full
Optuna sweep (blueprint section 17) — a legitimate result, not a shortcut.

Held-out test results (2025-2026 seasons, never seen during training or
calibration):

| Model | Log Loss | Brier | ROC-AUC | Accuracy |
|---|---|---|---|---|
| Random Forest (raw) | 0.497 | 0.161 | 0.872 | 0.775 |
| Random Forest + isotonic calibration | 0.531 | 0.156 | 0.871 | 0.753 |

Calibration slightly worsens log loss but improves the Brier score and
substantially closes the mean calibration-curve gap (predicted vs. observed
win frequency across probability deciles) — the raw model is overconfident
at the extremes, which isotonic regression corrects. This distinction
(ranking quality vs. probability trustworthiness) is exactly what blueprint
section 24 calls out; see the Model Insights page for the full curve.

`python -m src.models.predict` shows the inference interface the Streamlit
live win-probability page calls.

## Streamlit Application

```bash
streamlit run app/Home.py
```

Nine pages, all reading from the Parquet/CSV tables and the trained models
(no live API, no database dependency):

- **Home** — headline tournament numbers, featured players (with photos), navigation
- **Teams** — a card grid per team (colored badge, code, record, win %)
- **IPL Overview** — team win %, batting-first vs chasing, toss impact, matches per season
- **Player Analytics** — photo, batting/bowling career stats, run composition (1s/2s/3s/4s/5s/6s
  breakdown of career runs), dismissal-type breakdown, strike rate/economy by phase, recent form
- **Batter vs Bowler** — both players' photos, historical head-to-head, outcome distribution per ball
- **Venue Analytics** — photo, scoring conditions, chasing vs defending record, scoring by over
- **Live Win Probability** — a match-center header (final score both innings, result, venue) plus
  a Manhattan runs-per-over chart, then replays a real historical run chase ball-by-ball through
  the trained model, with a full-match probability timeline annotated with wickets and sixes
  (blueprint Modules 2 and 3)
- **Model Insights** — validation/test metrics, raw-vs-calibrated calibration curves, methodology
- **Player Performance Predictor** — expected runs/strike rate/probability thresholds for
  a player/opponent/venue combination

All 9 pages are checked with Streamlit's `AppTest` headless runner (including
widget interactions — changing the selected match/player/matchup) as part of
verifying this works, not just that it imports.

### Visual Design

Dark navy theme (`.streamlit/config.toml`) plus a shared CSS/component layer
(`app/components.py`: `inject_theme_css`, `render_team_badge`,
`render_match_banner`) styled after broadcast-style match-center UIs.
Deliberately **not** using official team crests — those are trademarked, and
hotlinking them on a public deployment is a real IP risk — team identity is
instead a colored badge with the team's short code (CSK, MI, RCB, ...),
generated from data already in the app. Also deliberately **not** attempting
a wagon wheel, spider chart, or catch map: those need ball-tracking data
(shot direction, fielding position) that Cricsheet — this project's only
data source — simply doesn't record. Building them would mean displaying
fabricated numbers as if they were real match data.

### Player & Venue Photos

Sourced from Wikimedia via `python -m src.data.fetch_photos`. Players are
matched by Wikidata property P2697 ("Cricinfo player ID") against the
`key_cricinfo` id already in `players.parquet` — an *exact* id match, not
name search. That distinction matters: an earlier name-search version of
this script (searching "JR Hazlewood cricketer" and checking the word
"cricket" appears on the result) confidently attached **Steve Smith's**
photo to Josh Hazlewood and the **IPL tournament logo** to Marcus Stoinis,
because initials-only names search ambiguously and "cricket" appears on
nearly every cricket-related Wikipedia page. An exact id join can't make
that mistake — a player with no matching Wikidata claim just gets no
photo, never a wrong one. Coverage: 348/805 players overall, but 45/50
(90%) of the top run-scorers — the players people actually look up.
Venues (no equivalent id available) use name search with a stricter
check — the venue's own distinguishing word must appear in the matched
page title — reaching 24/36 (67%). Everywhere a photo isn't found, the app
shows a generated colored-initials avatar instead of guessing.

## Player Performance Predictor

`python -m src.features.build_player_performance_features` builds a per-innings
feature table (one row per player/match/innings, 16.8K rows across 524
players) with strictly leakage-safe historical features: career average/
strike rate, last-5/last-10 innings form, season-to-date form, and
venue/opponent-specific averages — every one `.shift(1)`-ed so a row never
sees its own outcome.

`python -m src.models.train_player_performance` compares Linear Regression
against a Random Forest (chronological split, same season boundaries as the
win-probability model) and deploys the Random Forest — not because it wins
on MAE (Linear Regression is statistically tied), but because only a tree
ensemble's per-tree prediction spread can produce the "Prediction Range" and
P(30+)/P(50+) outputs blueprint Module 6 asks for.

**Honest result**: on the 2025-2026 test seasons, the model's MAE (16.57)
beats a naive "always predict this player's career average" baseline
(16.82) by only ~1.5%. This isn't a bug — a single T20 innings score is
close to random around a player's underlying ability, so the realistic
ceiling here is low without richer inputs (which bowler, match situation,
weather). The Model Insights page reports this comparison directly rather
than hiding it.

`streamlit run app/Home.py` → **Player Performance Predictor** page lets you
pick any player/opponent/venue combination and see the live prediction.

## Tableau Dashboard

Power BI Desktop is Windows-only, so this project uses **Tableau Desktop**
instead for the BI-tool layer the blueprint calls for (business intelligence,
data modeling, executive dashboard design — a different skill set than the
Streamlit application).

`python -m src.analytics.build_stats_tables` produces the BI-ready exports:
`overview_kpis.csv`, `matches_bi.csv` (with `canonical_*` team columns
already applied), `team_stats.csv`, `head_to_head.csv`, `season_trends.csv`,
`venue_stats.csv`, `phase_trends.csv`, and `batting_stats.csv`/
`bowling_stats.csv` (now with each player's `current_team` for filtering).

A Tableau workbook is normally built through its GUI, with no API for
authoring one programmatically — so `dashboard/IPL_Intelligence.twb` was
hand-written against Tableau's XML schema and genuinely tested (not written
blind): opened in the real Tableau Desktop install on this machine, its own
log file read after each attempt for exact DTD validation errors, each one
fixed and retested. Real bugs were caught and fixed this way. What's
*unverified*: this session's environment can't actually render a GUI
window to look at (screenshots only ever showed the desktop/VS Code, never
Tableau, even with the process confirmed alive and logging a successful
render), and the CSV data connection currently loads 0 rows for a reason
that needs visual iteration to pin down. Full account, and the four-page
build guide (mapped 1:1 to blueprint section 37's Power BI pages) for
finishing this on a machine with a real display: [`dashboard/TABLEAU_GUIDE.md`](dashboard/TABLEAU_GUIDE.md).

## Team-Name Normalization

Cricsheet records the name a team played under at the time (blueprint
section 42). `src/data/team_normalization.py` merges historical renames
(e.g. "Royal Challengers Bangalore" -> "Bengaluru", a typo-only variant of
"Rising Pune Supergiant(s)") into one canonical name for analytics, while
keeping genuinely distinct franchises that share a city separate (Deccan
Chargers vs Sunrisers Hyderabad, Gujarat Lions vs Gujarat Titans). The
source tables (`matches.parquet`) are never overwritten — normalization is
applied at analysis time only.

## Venue Normalization

The same gap existed for venues (blueprint section 43) and was found while
writing `sql/analytics_queries.sql`'s venue-profile query: "Wankhede
Stadium" and "Wankhede Stadium, Mumbai" showed up as two separate rows.
`src/data/venue_normalization.py` merges 24 name variants down from 60 raw
venue strings to 36 canonical venues — plain suffix/punctuation variants
(`"M.Chinnaswamy Stadium"` vs `"M Chinnaswamy Stadium, Bengaluru"`) plus
three well-documented ground renames (Feroz Shah Kotla -> Arun Jaitley
Stadium, Sardar Patel Stadium -> Narendra Modi Stadium, Subrata Roy Sahara
Stadium -> Maharashtra Cricket Association Stadium).

This wasn't just a descriptive-analytics bug — venue is a feature in both
ML models, so the fragmentation was diluting its signal. After the fix and
retrain, Logistic Regression's validation log loss improved from 0.590 to
0.523 (ROC-AUC 0.828 -> 0.852); Random Forest improved more modestly (it's
less sensitive to sparse one-hot categories). Applied everywhere venue is
grouped or filtered: descriptive stats, both feature-engineering pipelines,
the Streamlit Venue Analytics page, and the PostgreSQL load (`fact_matches`
keeps `venue_original` alongside the canonical `venue`, same audit-trail
pattern as team names).

## Development Roadmap

- [x] Repository + environment setup
- [x] Cricsheet IPL data download
- [x] JSON parser -> matches / deliveries / players tables
- [x] Data validation
- [x] Descriptive analytics (batting/bowling/team/venue stats, tournament overview)
- [x] Team-name normalization
- [x] Venue normalization
- [x] PostgreSQL schema, loaded and verified (Postgres.app, no Homebrew)
- [x] SQL demonstrations: CTEs, window functions, rolling averages, ranking, LAG, views, FILTER
- [x] Feature engineering (match-state, momentum) for win probability
- [x] Full model comparison (Logistic Regression, Random Forest, XGBoost, LightGBM) + isotonic calibration
- [x] Streamlit application (8 pages: Home, Overview, Player Analytics, Batter vs Bowler, Venue Analytics, Win Probability, Model Insights, Player Performance Predictor)
- [x] Batter-vs-bowler matchup engine (historical; model-based next-ball distribution not yet built)
- [x] Player performance predictor
- [ ] Tableau dashboard (data + build guide ready — see below; the workbook itself needs to be assembled in the Tableau GUI, which isn't something that can be scripted/verified the way the rest of this repo is)
- [ ] Deployment

## Future Improvements

Player performance predictor, live match integration, Win Probability Added
(WPA) player-impact metric, expected-runs modeling — see the full project
blueprint for the complete roadmap.
