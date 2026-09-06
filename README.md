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
- [x] Streamlit application (7 pages: Home, Overview, Player Analytics, Batter vs Bowler, Venue Analytics, Win Probability, Model Insights)
- [ ] Power BI dashboard
- [ ] Batter-vs-bowler matchup engine
- [ ] Player performance predictor
- [ ] Deployment

## Future Improvements

Player performance predictor, live match integration, Win Probability Added
(WPA) player-impact metric, expected-runs modeling — see the full project
blueprint for the complete roadmap.
