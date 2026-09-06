"""Build the second-innings, ball-by-ball feature table for the win
probability model (blueprint sections 20, 21, 25).

Every row is a match state immediately after one delivery of the run
chase (innings 2, excluding super overs). The label is whether the
batting/chasing team went on to win the actual match. Only information
knowable at that point in time is used — see the "no leakage" list below.

Usage:
    python -m src.features.build_features
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.team_normalization import canonical_team_name

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
FEATURES_DIR = BASE_DIR / "data" / "features"

# Deliberately excluded from every feature row: final match winner, final
# score/wickets, player_of_match, win margin, method (D/L) — anything only
# known once the match (or even just this innings) has finished.
MOMENTUM_WINDOWS = (6, 12, 18)


def _first_innings_totals(deliveries: pd.DataFrame) -> pd.Series:
    main = deliveries[~deliveries["is_super_over"]]
    return main[main["innings"] == 1].groupby("match_id")["runs_total"].sum().rename("first_innings_total")


def build_win_prediction_features(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    # Only matches with a real, decided run chase can supply training labels.
    eligible_matches = matches[matches["winner"].notna()].copy()
    for col in ["team1", "team2", "toss_winner", "winner"]:
        eligible_matches[col] = eligible_matches[col].map(canonical_team_name, na_action="ignore")

    first_innings_total = _first_innings_totals(deliveries)

    second_innings = deliveries[
        (deliveries["innings"] == 2) & (~deliveries["is_super_over"]) & (deliveries["match_id"].isin(eligible_matches["match_id"]))
    ].copy()
    for col in ["batting_team", "bowling_team"]:
        second_innings[col] = second_innings[col].map(canonical_team_name, na_action="ignore")

    second_innings = second_innings.sort_values(["match_id", "over", "ball"]).reset_index(drop=True)
    second_innings = second_innings.merge(first_innings_total, on="match_id", how="inner")
    second_innings = second_innings.merge(
        eligible_matches[["match_id", "season_year", "date", "venue", "winner", "overs_per_innings"]],
        on="match_id",
        how="inner",
        suffixes=("", "_match"),
    )

    grouped = second_innings.groupby("match_id", sort=False)
    is_legal = (second_innings["extra_wides"] == 0) & (second_innings["extra_noballs"] == 0)

    second_innings["balls_bowled"] = is_legal.groupby(second_innings["match_id"]).cumsum()
    second_innings["current_score"] = grouped["runs_total"].cumsum()
    second_innings["current_wickets"] = grouped["is_wicket"].cumsum()

    for window in MOMENTUM_WINDOWS:
        second_innings[f"last_{window}_runs"] = grouped["runs_total"].transform(
            lambda s, w=window: s.rolling(w, min_periods=1).sum()
        )
    second_innings["wickets_last_6"] = grouped["is_wicket"].transform(
        lambda s: s.rolling(6, min_periods=1).sum()
    )
    second_innings["wickets_last_12"] = grouped["is_wicket"].transform(
        lambda s: s.rolling(12, min_periods=1).sum()
    )

    target_runs = second_innings["first_innings_total"] + 1
    total_legal_balls = second_innings["overs_per_innings"] * 6

    second_innings["target_runs"] = target_runs
    second_innings["balls_remaining"] = (total_legal_balls - second_innings["balls_bowled"]).clip(lower=0)
    second_innings["runs_required"] = target_runs - second_innings["current_score"]
    second_innings["wickets_remaining"] = 10 - second_innings["current_wickets"]
    second_innings["current_run_rate"] = np.where(
        second_innings["balls_bowled"] > 0,
        second_innings["current_score"] / second_innings["balls_bowled"] * 6,
        0.0,
    )
    second_innings["required_run_rate"] = np.where(
        second_innings["balls_remaining"] > 0,
        second_innings["runs_required"].clip(lower=0) / second_innings["balls_remaining"] * 6,
        0.0,
    )

    second_innings["label"] = (second_innings["batting_team"] == second_innings["winner"]).astype(int)

    feature_columns = [
        "delivery_id",
        "match_id",
        "season_year",
        "date",
        "venue",
        "batting_team",
        "bowling_team",
        "over",
        "ball",
        "phase",
        "target_runs",
        "current_score",
        "current_wickets",
        "balls_bowled",
        "balls_remaining",
        "runs_required",
        "wickets_remaining",
        "current_run_rate",
        "required_run_rate",
        "last_6_runs",
        "last_12_runs",
        "last_18_runs",
        "wickets_last_6",
        "wickets_last_12",
        "label",
    ]
    return second_innings[feature_columns].reset_index(drop=True)


def main() -> None:
    matches = pd.read_parquet(PROCESSED_DIR / "matches.parquet")
    deliveries = pd.read_parquet(PROCESSED_DIR / "deliveries.parquet")

    features = build_win_prediction_features(matches, deliveries)

    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FEATURES_DIR / "win_prediction_features.parquet"
    features.to_parquet(out_path, index=False)

    print(f"win_prediction_features: {len(features):,} rows, {features['match_id'].nunique():,} matches -> {out_path}")
    print(f"label balance: {features['label'].mean():.3f} chasing-team win rate")


if __name__ == "__main__":
    main()
