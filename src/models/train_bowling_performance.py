"""Train the Bowling Performance Predictor — bowling-side counterpart to
train_player_performance.py.

Same chronological, leakage-safe discipline:
    TRAIN      <= 2022
    VALIDATION 2023-2024
    TEST       2025-2026

Compares Linear Regression against a Random Forest Regressor (picked by
validation MAE) for wickets taken, then reports MAE/RMSE/R2 on the held-out
test seasons. The saved model is a Random Forest specifically so the app
can read the spread of individual trees' predictions to produce a
prediction range and P(2+)/P(3+) wickets — no separate classifiers needed.

Usage:
    python -m src.models.train_bowling_performance
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
FEATURES_PATH = BASE_DIR / "data" / "features" / "bowling_performance_features.parquet"
MODELS_DIR = BASE_DIR / "models"

CATEGORICAL_FEATURES = ["venue", "bowling_team", "batting_team"]
NUMERIC_FEATURES = [
    "career_avg_wickets",
    "career_economy",
    "last_5_avg_wickets",
    "last_10_avg_wickets",
    "last_5_economy",
    "season_avg_wickets",
    "venue_avg_wickets",
    "opponent_avg_wickets",
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
            n_estimators=300, max_depth=6, min_samples_leaf=5, n_jobs=-1, random_state=42
        ),
    }


def main() -> None:
    features = pd.read_parquet(FEATURES_PATH)
    train, val, test = chronological_split(features)
    print(
        f"train: {len(train):,} matches, <= {TRAIN_MAX_SEASON}\n"
        f"val:   {len(val):,} matches, {VAL_SEASONS[0]}-{VAL_SEASONS[1]}\n"
        f"test:  {len(test):,} matches, >= {TEST_MIN_SEASON}\n"
    )

    X_train, y_train = train[FEATURE_COLUMNS], train["label_wickets"]
    X_val, y_val = val[FEATURE_COLUMNS], val["label_wickets"]
    X_test, y_test = test[FEATURE_COLUMNS], test["label_wickets"]

    # Auxiliary model: expected economy, reported alongside expected
    # wickets. Not the headline-evaluated target, so a single Random
    # Forest (matching the deployed wickets model) is enough.
    economy_pipeline = Pipeline([("preprocess", build_preprocessor()), ("model", RandomForestRegressor(
        n_estimators=300, max_depth=6, min_samples_leaf=5, n_jobs=-1, random_state=42
    ))])
    economy_pipeline.fit(X_train, train["label_economy"])
    economy_test_metrics = compute_regression_metrics(test["label_economy"], economy_pipeline.predict(X_test))

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

    # Deploy the Random Forest even if Linear Regression wins narrowly on
    # validation MAE: only a tree ensemble's per-tree spread can produce
    # the prediction range and P(2+)/P(3+) wickets outputs.
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

    # Naive baseline: always predict this bowler's career average wickets.
    naive_pred = test["career_avg_wickets"]
    naive_metrics = compute_regression_metrics(y_test, naive_pred)
    print("[naive: career average] test metrics: " + ", ".join(f"{k}={v:.4f}" for k, v in naive_metrics.items()))
    print("[economy model] test metrics: " + ", ".join(f"{k}={v:.4f}" for k, v in economy_test_metrics.items()))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": deployed_pipeline,
            "economy_model": economy_pipeline,
            "feature_columns": FEATURE_COLUMNS,
            "model_name": deployed_name,
        },
        MODELS_DIR / "bowling_performance.pkl",
    )

    evaluation_report = {
        "candidate_validation_metrics": results,
        "best_by_validation_mae": best_by_mae,
        "deployed_model": deployed_name,
        "test_metrics": test_metrics,
        "naive_baseline_test_metrics": naive_metrics,
        "economy_model_test_metrics": economy_test_metrics,
    }
    with open(MODELS_DIR / "bowling_performance_evaluation.json", "w") as f:
        json.dump(evaluation_report, f, indent=2)

    print(f"\nSaved model -> {MODELS_DIR / 'bowling_performance.pkl'}")
    print(f"Saved evaluation report -> {MODELS_DIR / 'bowling_performance_evaluation.json'}")


if __name__ == "__main__":
    main()
