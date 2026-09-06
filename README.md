# IPL Intelligence — Cricket Analytics & Win Prediction Platform

An end-to-end cricket analytics platform built on 19 seasons (2008-2026) of IPL
ball-by-ball data: Python data engineering, PostgreSQL/SQL, descriptive
analytics, a calibrated win-probability model, player analytics, venue
analysis, a batter-vs-bowler matchup engine, and an interactive Streamlit
application.

Status: **data foundation, descriptive analytics, and a calibrated win-probability
model are complete**, actively under development. See
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
                 Descriptive Analytics   Machine Learning   Power BI
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
├── dashboard/          # Power BI .pbix
└── app/                # Streamlit application
```

## Reproducing the Project

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.data.download_data          # fetch Cricsheet IPL JSON + player register
python -m src.data.parse_cricsheet        # build matches/deliveries/players tables
python -m src.data.validate_data          # sanity-check the parsed tables
python -m src.analytics.build_stats_tables  # batting/bowling/team/venue stats
python -m src.analytics.overview          # tournament headline numbers
python -m src.features.build_features     # win-probability feature table
python -m src.models.train                # train, calibrate, evaluate
python -m src.models.predict              # example live win-probability call

python -m src.features.build_player_performance_features  # player-performance feature table
python -m src.models.train_player_performance              # train, evaluate
python -m src.models.predict_player_performance             # example prediction

streamlit run app/Home.py                 # the full application
```

Current scale: **1,243 matches**, **295,732 deliveries**, **804 players**,
seasons 2008-2026.

## Win Probability Model

`python -m src.features.build_features` builds a ball-by-ball second-innings
feature table (142K balls across 1,234 decided matches). `python -m
src.models.train` does a chronological season split (train <=2022, validate
2023-2024, test >=2025), compares Logistic Regression vs Random Forest,
calibrates the better model with isotonic regression, and saves it to
`models/win_probability.pkl`.

Held-out test results (2025-2026 seasons, never seen during training or
calibration):

| Model | Log Loss | Brier | ROC-AUC | Accuracy |
|---|---|---|---|---|
| Random Forest (raw) | 0.496 | 0.159 | 0.872 | 0.773 |
| Random Forest + isotonic calibration | 0.513 | 0.155 | 0.871 | 0.759 |

Calibration slightly worsens log loss but improves the Brier score and
roughly halves the mean calibration-curve gap (0.115 -> 0.089 average
|predicted - observed| across probability deciles) — the raw model is
overconfident at the extremes, which isotonic regression corrects. This
distinction (ranking quality vs. probability trustworthiness) is exactly
what blueprint section 24 calls out.

**XGBoost/LightGBM are not yet in the comparison** — both need `libomp`,
which isn't installed (no Homebrew in this environment). `brew install
libomp` (or a Docker-based dev environment) unblocks adding them later;
they're expected to beat the Random Forest baseline.

`python -m src.models.predict` shows the inference interface the Streamlit
live win-probability page calls.

## Streamlit Application

```bash
streamlit run app/Home.py
```

Seven pages, all reading from the Parquet/CSV tables and the trained model
(no live API, no database dependency):

- **Home** — headline tournament numbers, featured players, navigation
- **IPL Overview** — team win %, batting-first vs chasing, toss impact, matches per season
- **Player Analytics** — batting/bowling career stats, strike rate/economy by phase, recent form
- **Batter vs Bowler** — historical head-to-head, outcome distribution per ball
- **Venue Analytics** — scoring conditions, chasing vs defending record, scoring by over
- **Live Win Probability** — replays a real historical run chase ball-by-ball through the
  trained model, with a full-match probability timeline annotated with wickets and sixes
  (blueprint Modules 2 and 3)
- **Model Insights** — validation/test metrics, raw-vs-calibrated calibration curves, methodology

All 7 pages are checked with Streamlit's `AppTest` headless runner (including
widget interactions — changing the selected match/player/matchup) as part of
verifying this works, not just that it imports.

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

**What's not automatable**: a Tableau workbook is built through its GUI —
there's no way to author or verify a `.twbx` file the way the rest of this
repo's output is checked (tests, `AppTest`, validation scripts). See
[`dashboard/TABLEAU_GUIDE.md`](dashboard/TABLEAU_GUIDE.md) for the exact
worksheets/dashboards to build, mapped 1:1 to the four Power BI pages the
blueprint originally specified (section 37).

## Team-Name Normalization

Cricsheet records the name a team played under at the time (blueprint
section 42). `src/data/team_normalization.py` merges historical renames
(e.g. "Royal Challengers Bangalore" -> "Bengaluru", a typo-only variant of
"Rising Pune Supergiant(s)") into one canonical name for analytics, while
keeping genuinely distinct franchises that share a city separate (Deccan
Chargers vs Sunrisers Hyderabad, Gujarat Lions vs Gujarat Titans). The
source tables (`matches.parquet`) are never overwritten — normalization is
applied at analysis time only.

## Development Roadmap

- [x] Repository + environment setup
- [x] Cricsheet IPL data download
- [x] JSON parser -> matches / deliveries / players tables
- [x] Data validation
- [x] Descriptive analytics (batting/bowling/team/venue stats, tournament overview)
- [x] Team-name normalization
- [x] PostgreSQL schema (not yet loaded — no local Postgres in this environment)
- [x] Feature engineering (match-state, momentum) for win probability
- [x] Baseline ML (Logistic Regression, Random Forest) + isotonic calibration
- [ ] XGBoost / LightGBM (blocked on libomp)
- [x] Streamlit application (8 pages: Home, Overview, Player Analytics, Batter vs Bowler, Venue Analytics, Win Probability, Model Insights, Player Performance Predictor)
- [x] Batter-vs-bowler matchup engine (historical; model-based next-ball distribution not yet built)
- [x] Player performance predictor
- [ ] Tableau dashboard (data + build guide ready — see below; the workbook itself needs to be assembled in the Tableau GUI, which isn't something that can be scripted/verified the way the rest of this repo is)
- [ ] Deployment

## Future Improvements

Player performance predictor, live match integration, Win Probability Added
(WPA) player-impact metric, expected-runs modeling — see the full project
blueprint for the complete roadmap.
