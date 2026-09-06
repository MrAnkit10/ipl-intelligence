"""Train the Player Performance Predictor (blueprint Module 6).

Same chronological, leakage-safe discipline as the win-probability model:
    TRAIN      <= 2022
    VALIDATION 2023-2024
    TEST       2025-2026

Compares Linear Regression against a Random Forest Regressor (picked by
validation MAE), then reports MAE/RMSE/R2 on the held-out test seasons.
The saved model is a Random Forest specifically so the app can read the
spread of individual trees' predictions to produce a prediction range and
P(30+)/P(50+) — no separate classifiers needed for that.

Usage:
    python -m src.models.train_player_performance
"""

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.models.evaluate import compute_regression_metrics

BASE_DIR = Path(__file__).resolve().parents[2]
FEATURES_PATH = BASE_DIR / "data" / "features" / "player_performance_features.parquet"
MODELS_DIR = BASE_DIR / "models"

CATEGORICAL_FEATURES = ["venue", "batting_team", "bowling_team"]
NUMERIC_FEATURES = [
    "batting_position",
    "career_avg_runs",
    "career_strike_rate",
    "last_5_avg_runs",
    "last_10_avg_runs",
    "last_5_strike_rate",
    "season_avg_runs",
    "venue_avg_runs",
    "opponent_avg_runs",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

TRAIN_MAX_SEASON = 2022
VAL_SEASONS = (2023, 2024)
TEST_MIN_SEASON = 2025


def chronological_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df[df["season_year"] <= TRAIN_MAX_SEASON]
    val = df[df["season_year"].between(*VAL_SEASONS)]
    test = df[df["season_year"] >= TEST_MIN_SEASON]
    return train, val, test


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
        ]
    )


def candidate_models() -> dict:
    return {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=300, min_samples_leaf=5, n_jobs=-1, random_state=42
        ),
    }


def main() -> None:
    features = pd.read_parquet(FEATURES_PATH)
    train, val, test = chronological_split(features)
    print(
        f"train: {len(train):,} innings, <= {TRAIN_MAX_SEASON}\n"
        f"val:   {len(val):,} innings, {VAL_SEASONS[0]}-{VAL_SEASONS[1]}\n"
        f"test:  {len(test):,} innings, >= {TEST_MIN_SEASON}\n"
    )

    X_train, y_train = train[FEATURE_COLUMNS], train["label_runs"]
    X_val, y_val = val[FEATURE_COLUMNS], val["label_runs"]
    X_test, y_test = test[FEATURE_COLUMNS], test["label_runs"]

    # Auxiliary model: expected balls faced, so expected strike rate =
    # expected_runs / expected_balls * 100 is a real derived quantity
    # rather than a guess. Not the headline-evaluated target, so a single
    # Random Forest (matching the deployed runs model) is enough.
    balls_pipeline = Pipeline([("preprocess", build_preprocessor()), ("model", RandomForestRegressor(
        n_estimators=300, min_samples_leaf=5, n_jobs=-1, random_state=42
    ))])
    balls_pipeline.fit(X_train, train["label_balls_faced"])
    balls_test_metrics = compute_regression_metrics(test["label_balls_faced"], balls_pipeline.predict(X_test))

    results = {}
    fitted_pipelines = {}
    for name, model in candidate_models().items():
        pipeline = Pipeline([("preprocess", build_preprocessor()), ("model", model)])
        pipeline.fit(X_train, y_train)
        val_pred = pipeline.predict(X_val)
        metrics = compute_regression_metrics(y_val, val_pred)
        results[name] = metrics
        fitted_pipelines[name] = pipeline
        print(f"[{name}] validation: " + ", ".join(f"{k}={v:.4f}" for k, v in metrics.items()))

    best_by_mae = min(results, key=lambda n: results[n]["mae"])

    # Deliberately deploy the Random Forest even if Linear Regression has a
    # marginally lower validation MAE (it usually does, by a hair): only a
    # tree ensemble's per-tree spread can produce the "Prediction Range" and
    # P(30+)/P(50+) outputs Module 6 actually requires. This is reported
    # honestly below rather than silently picking whichever wins on MAE.
    deployed_name = "random_forest"
    deployed_pipeline = fitted_pipelines[deployed_name]
    print(
        f"\nBest by validation MAE: {best_by_mae} | Deployed: {deployed_name} "
        f"(needs per-tree spread for range/probability outputs)"
    )

    test_metrics = {}
    for name, pipeline in fitted_pipelines.items():
        test_metrics[name] = compute_regression_metrics(y_test, pipeline.predict(X_test))
        print(f"[{name}] test metrics: " + ", ".join(f"{k}={v:.4f}" for k, v in test_metrics[name].items()))

    # Naive baseline for comparison: always predict this player's career
    # average. If the model can't beat this it isn't adding value.
    naive_pred = test["career_avg_runs"]
    naive_metrics = compute_regression_metrics(y_test, naive_pred)
    print("[naive: career average] test metrics: " + ", ".join(f"{k}={v:.4f}" for k, v in naive_metrics.items()))
    print("[balls_faced model] test metrics: " + ", ".join(f"{k}={v:.4f}" for k, v in balls_test_metrics.items()))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": deployed_pipeline,
            "balls_model": balls_pipeline,
            "feature_columns": FEATURE_COLUMNS,
            "model_name": deployed_name,
        },
        MODELS_DIR / "player_performance.pkl",
    )

    evaluation_report = {
        "candidate_validation_metrics": results,
        "best_by_validation_mae": best_by_mae,
        "deployed_model": deployed_name,
        "test_metrics": test_metrics,
        "naive_baseline_test_metrics": naive_metrics,
        "balls_faced_model_test_metrics": balls_test_metrics,
    }
    with open(MODELS_DIR / "player_performance_evaluation.json", "w") as f:
        json.dump(evaluation_report, f, indent=2)

    print(f"\nSaved model -> {MODELS_DIR / 'player_performance.pkl'}")
    print(f"Saved evaluation report -> {MODELS_DIR / 'player_performance_evaluation.json'}")


if __name__ == "__main__":
    main()
