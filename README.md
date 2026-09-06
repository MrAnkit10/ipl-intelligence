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
| **Random Forest (selected)** | **0.467** | **0.868** |
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
| Random Forest (raw) | 0.486 | 0.158 | 0.882 | 0.776 |
| Random Forest + isotonic calibration | 0.485 | 0.148 | 0.880 | 0.792 |

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

Thirteen pages, all reading from the Parquet/CSV tables and the trained
models (no live API, no database dependency), Model Insights deliberately
last in the nav order since it's project internals rather than something a
visitor explores first:

- **Home** — headline tournament numbers, a season-archive quick-launch row (2008-2026, one
  click into that season's full match list), a redesigned "Explore" grid, top run-scorers and
  top wicket-takers as team-tinted photo cards
- **Teams** — a card grid per team (colored badge, code, record, win %); "View Full Stats" drills into...
- **Team Detail** — full record, head-to-head vs every opponent, leading batter/bowler
  (broadcast-style stat cards including highest score / best bowling figures), and a complete
  match log that opens straight into...
- **Season Archive** — every IPL season 2008-2026: matches played, the champion (derived as the
  winner of that season's chronologically-last match), Season Awards (Orange Cap, Purple Cap,
  and the final's Player of the Match, each with a photo), and every match with its own Player
  of the Match, each opening into...
- **Match Scorecard** — a full traditional scorecard reconstructed from ball-by-ball data for
  any of the 1,243 matches: batting card (runs/balls/4s/6s/SR/how out), bowling figures
  (overs/maidens/runs/wickets/economy), extras, and fall of wickets — verified against a real,
  independently-checkable match (SRH 207/4 beat RCB 172 by 35 runs, IPL 2017 match 1) before
  trusting it at scale
- **IPL Overview** — tournament leaders (top scorer/wicket-taker stat cards with highest score
  / best bowling figures), team win %, batting-first vs chasing, toss impact, matches-per-season
  trend, and full ranked leaderboards (every player, not just the top 3) for runs and wickets
- **Player Analytics** — photo, identity strip (role, seasons active, debut/last played —
  computed from every appearance so it's correct for bowlers too, not just batters), a
  **Career Dossier** percentile radar for batters (12 rate-stat axes — boundary %, six rate,
  chase/death strike rate, average, conversion, dot %, and more — ranked against players with
  15+ innings) and an equivalent **Bowling Dossier** for bowlers (9 axes — wickets/match, best
  figures, economy by phase, control — ranked against bowlers with 300+ balls bowled), a
  **Scoring Wheel** (career runs by shot value, 1s through 6s, as a polar chart), dismissal-type
  breakdown, strike rate/economy by phase, and recent form
- **Batter vs Bowler** — a split team-color matchup banner (both players' photos), historical
  head-to-head, and a donut chart of outcome distribution per ball
- **Venue Analytics** — photo, scoring conditions, chasing vs defending record, and a
  scoring-by-over trend line (each over's actual total, not a per-ball average, averaged across
  every innings played there)
- **Live Win Probability** — a match-center header (final score both innings, result, venue) plus
  a Manhattan runs-per-over chart, then replays a real historical run chase ball-by-ball through
  the trained model, with a full-match probability timeline annotated with wickets and sixes
  (blueprint Modules 2 and 3)
- **Player Performance Predictor** — a gauge-chart expected-runs prediction, milestone
  probability bars, and a form-comparison chart (career/recent/season/venue/opponent averages)
  for a player/opponent/venue combination
- **Records & Milestones** — biggest wins (by runs and by wickets), highest/lowest completed
  team totals, best partnerships for any wicket, and fastest fifties/hundreds plus most
  sixes/fours in a single innings
- **Player Comparison** — pick any two batters and see career stats side-by-side plus an
  overlaid percentile radar (the Career Dossier's own metrics) to compare how they each rank
  against the league on the same axes
- **Model Insights** — validation/test metrics, raw-vs-calibrated calibration curves, methodology

All pages are checked with Streamlit's `AppTest` headless runner (including
widget interactions and full navigation flows — Home → Teams → Team Detail,
Home → Seasons → Match Scorecard, Team Detail's match log → Match Scorecard
— via `st.switch_page`) as part of verifying this works, not just that it
imports. This caught a real bug during the page renumbering below: `Home.py`
still linked to pre-rename filenames, which only surfaced once tested through
the full app context rather than as an isolated page.

`AppTest` only checks that Streamlit's element tree builds without a Python
exception — it does not render real HTML, so a separate class of bug slipped
through it entirely: `st.markdown(..., unsafe_allow_html=True)` snippets
that embedded a multi-line SVG or an f-string placeholder resolving to `""`
on its own line produced a blank line in the middle of the HTML, which
Streamlit's markdown parser treats as the end of the "raw HTML" block —
everything after it renders as escaped, literal text instead. Fixed with a
`render_html()` helper (`app/components.py`) that collapses all whitespace
to single spaces before handing the string to `st.markdown`, used everywhere
the app builds custom card markup.

### Visual Design

Dark navy theme (`.streamlit/config.toml`) plus a shared CSS/component layer
(`app/components.py`: `inject_theme_css`, `render_page_title`, `chart_card`,
`render_team_badge`, `render_match_banner`, `render_matchup_banner`,
`render_stat_card`) styled after broadcast-style match-center UIs, adopting
a design reference the user shared from iplt20.com. No emoji anywhere in
page titles — a small custom SVG cricket-ball mark (`BALL_ICON_SVG`) stands
in instead. Deliberately **not** using official team crests or the IPL
logo — those are trademarked, and reproducing them (even redrawn) on a
public deployment is a real IP risk — team identity is instead a colored
badge with the team's short code (CSK, MI, RCB, ...), generated from data
already in the app. Also deliberately **not** attempting a wagon wheel,
spider chart, catch map, or bowling-length breakdown (all requested,
referencing real broadcast graphics) — those need ball-tracking data (shot
direction, pitch length) that Cricsheet, this project's only data source,
simply doesn't record. Building them would mean displaying fabricated
numbers as if they were real match data; what's genuine from those
references (the dark stat-card look) was extracted and reused instead.

### Data Accuracy

Asked to verify the numbers against the official IPL site and other
citable sources — iplt20.com is a JS-heavy commercial site that can't be
bulk-scraped, but its content (and Wikipedia's, and ESPNcricinfo's) can be
spot-checked and cross-referenced by hand, which is what caught the one
real data bug described below and then confirmed the fix.

**The bug, found by spotting an impossible stat**: the Seasons page once
showed Sachin Tendulkar with 982 runs and Chennai Super Kings as champion
for the 2009 season — neither is real (Tendulkar's actual best IPL season
was 618 runs in 2010; the real 2009 champion was Deccan Chargers).
Root cause: `_extract_season_year()` in `src/data/parse_cricsheet.py` took
the first 4 characters of Cricsheet's `season` field, which is a
split-year string for three IPL seasons — `"2007/08"`, `"2009/10"`,
`"2020/21"` — representing IPL **2008**, **2010**, and **2020**
respectively (every match in each falls entirely within that second
calendar year). Truncating `"2009/10"` to `"2009"` silently merged 60 real
IPL-2010 matches into the 57 real IPL-2009 matches, corrupting every
season-level number for that bucket. Fixed by deriving `season_year` from
the match's own first date instead of parsing the season label at all —
reliable here since no season in this dataset spans a calendar-year
boundary. The full pipeline (matches/deliveries tables, every descriptive
stat, both ML models) was rebuilt from raw Cricsheet JSON after the fix.

**Verification after the fix** — every value below is an exact match
against Wikipedia, ESPNcricinfo, or iplt20.com's own homepage:

| Check | This project | Independent source |
|---|---|---|
| 2008 champion / Orange Cap / Purple Cap | Rajasthan Royals / S Marsh 616 / Sohail Tanvir 22 | same (Wikipedia) |
| 2009 champion / Orange Cap / Purple Cap | Deccan Chargers / M Hayden 572 / RP Singh 23 | same (ESPNcricinfo) |
| 2010 champion / Orange Cap / Purple Cap | Chennai Super Kings / S Tendulkar 618 / P Ojha 21 | same (Wikipedia) |
| 2025 champion / Orange Cap / Purple Cap | Royal Challengers Bengaluru / Sai Sudharsan 759 / Prasidh Krishna 25 | same (Business Standard) |
| 2026 champion / Orange Cap / Purple Cap | Royal Challengers Bengaluru / V Sooryavanshi 776 / K Rabada 29 | same (iplt20.com homepage) |
| All 19 seasons' Orange Cap, Purple Cap, and Player of the Final | — | every one matches Wikipedia's season-by-season tables |
| Career runs / innings leader | V Kohli, 9,336 runs / 275 innings | same (Wikipedia) |
| Career wickets leader | YS Chahal, 233 wickets | same (Wikipedia) |
| Highest team total ever | SRH 287/3 (2024) | same |
| Lowest completed total ever | RCB 49 all out (2017) | same |
| Best partnership ever | de Villiers & Kohli, 229 runs (2016) | same |
| Fastest hundred ever | Chris Gayle, 30 balls (2013) | same (the legendary one) |
| 2026 final: date, venue, margin | 31 May 2026, Narendra Modi Stadium, RCB won by 5 wkts | same (iplt20.com's own match report) |

Separately, before this bug was found: Mumbai Indians' Wikipedia page
showed 273 matches / 151 wins / 55.31% at the time of checking; this
project's data through the *2025* season showed 277 matches / 151 wins /
55.31% — an exact match on wins and win %, meaning Wikipedia simply hadn't
been updated for the 2026 season yet. Not every mismatch against another
site is this project being wrong — but the Tendulkar case above shows it
sometimes is, which is exactly why every "does it match" claim in this
README is backed by a specific, checkable number rather than asserted.

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

**Honest result**: on the 2025-2026 test seasons, the model's MAE (16.49)
beats a naive "always predict this player's career average" baseline
(16.82) by only ~1.9%. This isn't a bug — a single T20 innings score is
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

## Season-Year Normalization

A third normalization gap, same shape as the two above but on `season_year`
rather than team or venue names — full story and the verification table
in [Data Accuracy](#data-accuracy). Short version: Cricsheet's `season`
field is a split-year string (`"2009/10"`) for three IPL seasons, and
naively parsing it merged two real tournaments (2009 and 2010) under one
label. Fixed in `src/data/parse_cricsheet.py` by deriving the year from
the match's own date instead of the season string.

## Records & Milestones

`src/analytics/records.py` computes classic cricket "records page" content
directly from `matches`/`deliveries` — biggest wins, highest/lowest
completed team totals, best partnerships (any wicket, by runs, found by
walking each innings ball-by-ball and grouping on the number of wickets
already down), and fastest fifties/hundreds plus most sixes/fours in a
single innings.

One implementation bug worth documenting: the first version defined
"fastest fifty/hundred" as *fewest total balls faced in the whole innings*
— which is a different, slower number than *balls taken to reach the
milestone* (a batter can reach 100 in 30 balls and then keep batting for
40 more balls scoring further runs). That first version would have missed
Chris Gayle's legendary 30-ball century entirely, since his innings was
175 off 66 balls total. Fixed by walking each innings ball-by-ball with a
cumulative-runs threshold crossing, which correctly surfaces it as the
all-time fastest hundred.

## Development Roadmap

- [x] Repository + environment setup
- [x] Cricsheet IPL data download
- [x] JSON parser -> matches / deliveries / players tables
- [x] Data validation
- [x] Descriptive analytics (batting/bowling/team/venue stats, tournament overview)
- [x] Team-name normalization
- [x] Venue normalization
- [x] Season-year normalization (found via an impossible stat: a merged 2009/2010 season)
- [x] PostgreSQL schema, loaded and verified (Postgres.app, no Homebrew)
- [x] SQL demonstrations: CTEs, window functions, rolling averages, ranking, LAG, views, FILTER
- [x] Feature engineering (match-state, momentum) for win probability
- [x] Full model comparison (Logistic Regression, Random Forest, XGBoost, LightGBM) + isotonic calibration
- [x] Streamlit application (13 pages, including a Season Archive with full ball-by-ball-derived match scorecards and season awards)
- [x] Batter-vs-bowler matchup engine (historical; model-based next-ball distribution not yet built)
- [x] Player performance predictor
- [x] Career Dossier / Bowling Dossier percentile radars and a two-player comparison tool
- [x] Records & Milestones page (biggest wins, extreme totals, partnerships, fastest milestones)
- [x] Deployment (Streamlit Community Cloud)
- [ ] Tableau dashboard (data + build guide ready — see below; the workbook itself needs to be assembled in the Tableau GUI, which isn't something that can be scripted/verified the way the rest of this repo is)

## Future Improvements

Model-based next-ball outcome distribution for the matchup engine, live
match integration, Win Probability Added (WPA) player-impact metric,
fielding stats beyond catches (run-outs, stumpings), and a bowler-style
Player Comparison page (currently batters only) — see the full project
blueprint for the complete roadmap.
