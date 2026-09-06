"""Build the per-innings feature table for the Player Performance Predictor
(blueprint Module 6).

Grain: one row per (player, match, innings) where the player faced at
least one ball. The label is the runs they scored in that innings.

Leakage discipline (same principle as the win-probability model, blueprint
section 21): every feature for a given innings uses only that player's
innings strictly BEFORE this match's date — never this innings' own
outcome, and never a future match. All rolling/expanding stats are
`.shift(1)`-ed per player before use.

Usage:
    python -m src.features.build_player_performance_features
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.team_normalization import canonical_team_name
from src.data.venue_normalization import canonical_venue_name

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
FEATURES_DIR = BASE_DIR / "data" / "features"

MIN_PRIOR_INNINGS = 3  # not enough history before this to make a meaningful prediction


def _batting_position(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Approximate batting position: rank players in an innings by the
    delivery_id at which they first appear as batter OR non-striker (so
    both openers rank 1-2 even though only one faces ball 1)."""
    appearances = pd.concat(
        [
            deliveries[["match_id", "innings", "delivery_id", "batter_id"]].rename(columns={"batter_id": "player_id"}),
            deliveries[["match_id", "innings", "delivery_id", "non_striker_id"]].rename(
                columns={"non_striker_id": "player_id"}
            ),
        ]
    )
    first_appearance = appearances.groupby(["match_id", "innings", "player_id"])["delivery_id"].min().reset_index()
    first_appearance["batting_position"] = first_appearance.groupby(["match_id", "innings"])["delivery_id"].rank(
        method="first"
    )
    return first_appearance[["match_id", "innings", "player_id", "batting_position"]]


def build_batting_innings(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, match, innings) actually batted in."""
    main = deliveries[~deliveries["is_super_over"]].copy()
    faced = main[main["extra_wides"] == 0]

    innings_agg = (
        faced.groupby(["match_id", "innings", "batter_id"])
        .agg(
            player_name=("batter", "first"),
            batting_team=("batting_team", "first"),
            bowling_team=("bowling_team", "first"),
            venue=("venue", "first"),
            date=("date", "first"),
            season_year=("season_year", "first"),
            runs=("runs_batter", "sum"),
            balls_faced=("runs_batter", "size"),
        )
        .reset_index()
        .rename(columns={"batter_id": "player_id"})
    )

    position = _batting_position(main)
    innings_agg = innings_agg.merge(position, on=["match_id", "innings", "player_id"], how="left")

    for col in ["batting_team", "bowling_team"]:
        innings_agg[col] = innings_agg[col].map(canonical_team_name, na_action="ignore")
    innings_agg["venue"] = innings_agg["venue"].map(canonical_venue_name, na_action="ignore")

    return innings_agg.sort_values(["player_id", "date"]).reset_index(drop=True)


def _shifted_expanding_mean(series: pd.Series) -> pd.Series:
    return series.shift(1).expanding().mean()


def _shifted_rolling_mean(series: pd.Series, window: int) -> pd.Series:
    return series.shift(1).rolling(window, min_periods=1).mean()


def _shifted_rolling_sum(series: pd.Series, window: int | None = None) -> pd.Series:
    shifted = series.shift(1)
    return shifted.expanding().sum() if window is None else shifted.rolling(window, min_periods=1).sum()


def add_historical_features(innings: pd.DataFrame) -> pd.DataFrame:
    innings = innings.copy()
    by_player = innings.groupby("player_id")

    innings["prior_innings_count"] = by_player["runs"].transform(lambda s: s.shift(1).expanding().count())
    innings["career_avg_runs"] = by_player["runs"].transform(_shifted_expanding_mean)
    innings["last_5_avg_runs"] = by_player["runs"].transform(lambda s: _shifted_rolling_mean(s, 5))
    innings["last_10_avg_runs"] = by_player["runs"].transform(lambda s: _shifted_rolling_mean(s, 10))

    # Strike rate = runs/balls computed from separately-shifted cumulative
    # sums, not row-wise averaged, so a few dot-ball innings don't skew it.
    career_runs = by_player["runs"].transform(lambda s: _shifted_rolling_sum(s))
    career_balls = by_player["balls_faced"].transform(lambda s: _shifted_rolling_sum(s))
    innings["career_strike_rate"] = np.where(career_balls > 0, career_runs / career_balls * 100, np.nan)

    last5_runs = by_player["runs"].transform(lambda s: _shifted_rolling_sum(s, 5))
    last5_balls = by_player["balls_faced"].transform(lambda s: _shifted_rolling_sum(s, 5))
    innings["last_5_strike_rate"] = np.where(last5_balls > 0, last5_runs / last5_balls * 100, np.nan)

    # Season form: expanding mean within player+season only, shifted.
    innings["season_avg_runs"] = innings.groupby(["player_id", "season_year"])["runs"].transform(
        _shifted_expanding_mean
    )

    innings["venue_avg_runs"] = innings.groupby(["player_id", "venue"])["runs"].transform(_shifted_expanding_mean)
    innings["opponent_avg_runs"] = innings.groupby(["player_id", "bowling_team"])["runs"].transform(
        _shifted_expanding_mean
    )

    # Sparse-history fallbacks: with no prior meeting at this venue/opponent,
    # fall back to career average rather than leaving a hole for the model.
    innings["venue_avg_runs"] = innings["venue_avg_runs"].fillna(innings["career_avg_runs"])
    innings["opponent_avg_runs"] = innings["opponent_avg_runs"].fillna(innings["career_avg_runs"])
    innings["season_avg_runs"] = innings["season_avg_runs"].fillna(innings["career_avg_runs"])

    return innings


def main() -> None:
    matches = pd.read_parquet(PROCESSED_DIR / "matches.parquet")
    deliveries = pd.read_parquet(PROCESSED_DIR / "deliveries.parquet")

    innings = build_batting_innings(matches, deliveries)
    innings = add_historical_features(innings)

    eligible = innings[innings["prior_innings_count"] >= MIN_PRIOR_INNINGS].copy()

    feature_columns = [
        "match_id",
        "innings",
        "player_id",
        "player_name",
        "date",
        "season_year",
        "batting_team",
        "bowling_team",
        "venue",
        "batting_position",
        "career_avg_runs",
        "career_strike_rate",
        "last_5_avg_runs",
        "last_10_avg_runs",
        "last_5_strike_rate",
        "season_avg_runs",
        "venue_avg_runs",
        "opponent_avg_runs",
        "runs",
        "balls_faced",
    ]
    result = eligible[feature_columns].rename(columns={"runs": "label_runs", "balls_faced": "label_balls_faced"})

    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FEATURES_DIR / "player_performance_features.parquet"
    result.to_parquet(out_path, index=False)
    print(f"player_performance_features: {len(result):,} rows, {result['player_id'].nunique():,} players -> {out_path}")


if __name__ == "__main__":
    main()
