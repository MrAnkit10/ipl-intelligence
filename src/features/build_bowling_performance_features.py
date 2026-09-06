"""Build the per-match feature table for the Bowling Performance Predictor
— the bowling-side counterpart to build_player_performance_features.py
(blueprint Module 6 covers "player performance" generally; this project
originally built only the batting half and added bowling afterward so a
bowler gets an actual bowling prediction instead of a meaningless
batting-runs one).

Grain: one row per (player, match) where the player bowled at least one
ball. The label is the wickets they took in that match.

Same leakage discipline as the batting version: every feature uses only
that player's matches strictly BEFORE this one — all rolling/expanding
stats are `.shift(1)`-ed per player before use.

Usage:
    python -m src.features.build_bowling_performance_features
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.bowling import BOWLER_CREDITED_DISMISSALS
from src.data.team_normalization import canonical_team_name
from src.data.venue_normalization import canonical_venue_name

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
FEATURES_DIR = BASE_DIR / "data" / "features"

MIN_PRIOR_MATCHES = 3  # not enough history before this to make a meaningful prediction


def build_bowling_matches(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, match) bowled in, with wickets/runs/balls for
    that match and the batting team faced (the bowling side's "opponent")."""
    main = deliveries[~deliveries["is_super_over"]].copy()
    legal = main[(main["extra_wides"] == 0) & (main["extra_noballs"] == 0)].copy()
    main["bowler_runs"] = main["runs_batter"] + main["extra_wides"] + main["extra_noballs"]

    wickets = (
        main[main["dismissal_kind"].isin(BOWLER_CREDITED_DISMISSALS)]
        .groupby(["match_id", "bowler_id"])
        .size()
        .rename("wickets")
    )
    balls = legal.groupby(["match_id", "bowler_id"]).size().rename("balls_bowled")
    runs = main.groupby(["match_id", "bowler_id"])["bowler_runs"].sum().rename("runs_conceded")

    identity = (
        main.groupby(["match_id", "bowler_id"])
        .agg(
            player_name=("bowler", "first"),
            bowling_team=("bowling_team", "first"),
            batting_team=("batting_team", "first"),
            venue=("venue", "first"),
            date=("date", "first"),
            season_year=("season_year", "first"),
        )
        .reset_index()
    )

    bowling_matches = identity.merge(balls, on=["match_id", "bowler_id"], how="left").merge(
        runs, on=["match_id", "bowler_id"], how="left"
    ).merge(wickets, on=["match_id", "bowler_id"], how="left")
    bowling_matches["wickets"] = bowling_matches["wickets"].fillna(0).astype(int)
    bowling_matches["balls_bowled"] = bowling_matches["balls_bowled"].fillna(0).astype(int)
    bowling_matches = bowling_matches[bowling_matches["balls_bowled"] > 0]

    bowling_matches["economy"] = np.where(
        bowling_matches["balls_bowled"] > 0,
        bowling_matches["runs_conceded"] / bowling_matches["balls_bowled"] * 6,
        np.nan,
    )

    for col in ["bowling_team", "batting_team"]:
        bowling_matches[col] = bowling_matches[col].map(canonical_team_name, na_action="ignore")
    bowling_matches["venue"] = bowling_matches["venue"].map(canonical_venue_name, na_action="ignore")

    bowling_matches = bowling_matches.rename(columns={"bowler_id": "player_id"})
    return bowling_matches.sort_values(["player_id", "date"]).reset_index(drop=True)


def _shifted_expanding_mean(series: pd.Series) -> pd.Series:
    return series.shift(1).expanding().mean()


def _shifted_rolling_mean(series: pd.Series, window: int) -> pd.Series:
    return series.shift(1).rolling(window, min_periods=1).mean()


def _shifted_rolling_sum(series: pd.Series, window: int | None = None) -> pd.Series:
    shifted = series.shift(1)
    return shifted.expanding().sum() if window is None else shifted.rolling(window, min_periods=1).sum()


def add_historical_features(bowling_matches: pd.DataFrame) -> pd.DataFrame:
    bm = bowling_matches.copy()
    by_player = bm.groupby("player_id")

    bm["prior_matches_count"] = by_player["wickets"].transform(lambda s: s.shift(1).expanding().count())
    bm["career_avg_wickets"] = by_player["wickets"].transform(_shifted_expanding_mean)
    bm["last_5_avg_wickets"] = by_player["wickets"].transform(lambda s: _shifted_rolling_mean(s, 5))
    bm["last_10_avg_wickets"] = by_player["wickets"].transform(lambda s: _shifted_rolling_mean(s, 10))

    career_runs = by_player["runs_conceded"].transform(lambda s: _shifted_rolling_sum(s))
    career_balls = by_player["balls_bowled"].transform(lambda s: _shifted_rolling_sum(s))
    bm["career_economy"] = np.where(career_balls > 0, career_runs / career_balls * 6, np.nan)

    last5_runs = by_player["runs_conceded"].transform(lambda s: _shifted_rolling_sum(s, 5))
    last5_balls = by_player["balls_bowled"].transform(lambda s: _shifted_rolling_sum(s, 5))
    bm["last_5_economy"] = np.where(last5_balls > 0, last5_runs / last5_balls * 6, np.nan)

    bm["season_avg_wickets"] = bm.groupby(["player_id", "season_year"])["wickets"].transform(_shifted_expanding_mean)
    bm["venue_avg_wickets"] = bm.groupby(["player_id", "venue"])["wickets"].transform(_shifted_expanding_mean)
    bm["opponent_avg_wickets"] = bm.groupby(["player_id", "batting_team"])["wickets"].transform(
        _shifted_expanding_mean
    )

    bm["venue_avg_wickets"] = bm["venue_avg_wickets"].fillna(bm["career_avg_wickets"])
    bm["opponent_avg_wickets"] = bm["opponent_avg_wickets"].fillna(bm["career_avg_wickets"])
    bm["season_avg_wickets"] = bm["season_avg_wickets"].fillna(bm["career_avg_wickets"])

    return bm


def main() -> None:
    matches = pd.read_parquet(PROCESSED_DIR / "matches.parquet")
    deliveries = pd.read_parquet(PROCESSED_DIR / "deliveries.parquet")

    bowling_matches = build_bowling_matches(matches, deliveries)
    bowling_matches = add_historical_features(bowling_matches)

    eligible = bowling_matches[bowling_matches["prior_matches_count"] >= MIN_PRIOR_MATCHES].copy()

    feature_columns = [
        "match_id",
        "player_id",
        "player_name",
        "date",
        "season_year",
        "bowling_team",
        "batting_team",
        "venue",
        "career_avg_wickets",
        "career_economy",
        "last_5_avg_wickets",
        "last_10_avg_wickets",
        "last_5_economy",
        "season_avg_wickets",
        "venue_avg_wickets",
        "opponent_avg_wickets",
        "wickets",
        "economy",
    ]
    result = eligible[feature_columns].rename(columns={"wickets": "label_wickets", "economy": "label_economy"})

    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FEATURES_DIR / "bowling_performance_features.parquet"
    result.to_parquet(out_path, index=False)
    print(f"bowling_performance_features: {len(result):,} rows, {result['player_id'].nunique():,} players -> {out_path}")


if __name__ == "__main__":
    main()
