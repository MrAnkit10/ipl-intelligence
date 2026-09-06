"""Train and evaluate win-probability models (blueprint sections 19-24).

Chronological, season-based split (never random-split individual
deliveries — that would leak same-match balls across train/test):
    TRAIN      <= 2022
    VALIDATION 2023-2024
    TEST       2025-2026

Compares Logistic Regression, Random Forest, XGBoost, and LightGBM, picks
the better one by validation log loss, calibrates it with isotonic
regression fit on the validation split, and reports final metrics on the
held-out test seasons. Saves the calibrated pipeline to
models/win_probability.pkl.

Usage:
    python -m src.models.train
"""

import json
from pathlib import Path

import joblib
import lightgbm
import pandas as pd
import xgboost
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.models.evaluate import compute_calibration_curve, compute_metrics

BASE_DIR = Path(__file__).resolve().parents[2]
FEATURES_PATH = BASE_DIR / "data" / "features" / "win_prediction_features.parquet"
MODELS_DIR = BASE_DIR / "models"

CATEGORICAL_FEATURES = ["venue", "batting_team", "bowling_team", "phase"]
NUMERIC_FEATURES = [
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
        "logistic_regression": LogisticRegression(max_iter=1000),
        # max_depth=10: an earlier unbounded-depth version scored worse on
        # validation (log_loss 0.481, AUC 0.853) than this bounded one
        # (0.467, 0.868) while pickling to 196MB vs 16MB — unconstrained
        # trees were overfitting, not adding signal. Bounding depth is a
        # straight improvement, not a size/accuracy tradeoff.
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=10, min_samples_leaf=5, n_jobs=-1, random_state=42
        ),
        # One-hot encoding venue/batting_team/bowling_team makes a wide,
        # sparse feature space where unregularized boosting overfits hard
        # (a first pass at n_estimators=300/depth=6 with no regularization
        # scored log_loss=0.68, worse than Random Forest's 0.49 — more
        # rounds made it worse still, up to 1.03, confirming overfitting
        # rather than undertraining). subsample/colsample/reg_lambda/
        # min_child_weight bring it back in range; a full Optuna sweep
        # (blueprint section 17) would likely close the remaining gap.
        "xgboost": xgboost.XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05, n_jobs=-1, random_state=42,
            eval_metric="logloss", subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0, min_child_weight=10,
        ),
        "lightgbm": lightgbm.LGBMClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05, n_jobs=-1, random_state=42, verbose=-1,
            subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0, min_child_samples=30,
        ),
    }


def main() -> None:
    features = pd.read_parquet(FEATURES_PATH)
    train, val, test = chronological_split(features)
    print(
        f"train: {len(train):,} balls ({train['match_id'].nunique()} matches, "
        f"<= {TRAIN_MAX_SEASON})\n"
        f"val:   {len(val):,} balls ({val['match_id'].nunique()} matches, "
        f"{VAL_SEASONS[0]}-{VAL_SEASONS[1]})\n"
        f"test:  {len(test):,} balls ({test['match_id'].nunique()} matches, "
        f">= {TEST_MIN_SEASON})\n"
    )

    X_train, y_train = train[FEATURE_COLUMNS], train["label"]
    X_val, y_val = val[FEATURE_COLUMNS], val["label"]
    X_test, y_test = test[FEATURE_COLUMNS], test["label"]

    results = {}
    fitted_pipelines = {}
    for name, model in candidate_models().items():
        pipeline = Pipeline([("preprocess", build_preprocessor()), ("model", model)])
        pipeline.fit(X_train, y_train)
        val_prob = pipeline.predict_proba(X_val)[:, 1]
        metrics = compute_metrics(y_val, val_prob)
        results[name] = metrics
        fitted_pipelines[name] = pipeline
        print(f"[{name}] validation: " + ", ".join(f"{k}={v:.4f}" for k, v in metrics.items()))

    best_name = min(results, key=lambda n: results[n]["log_loss"])
    best_pipeline = fitted_pipelines[best_name]
    print(f"\nBest model by validation log loss: {best_name}")

    raw_test_prob = best_pipeline.predict_proba(X_test)[:, 1]
    raw_test_metrics = compute_metrics(y_test, raw_test_prob)
    print(f"[{best_name}] raw test metrics: " + ", ".join(f"{k}={v:.4f}" for k, v in raw_test_metrics.items()))

    calibrated = CalibratedClassifierCV(FrozenEstimator(best_pipeline), method="isotonic")
    calibrated.fit(X_val, y_val)

    calibrated_test_prob = calibrated.predict_proba(X_test)[:, 1]
    calibrated_test_metrics = compute_metrics(y_test, calibrated_test_prob)
    print(
        f"[{best_name} + isotonic calibration] test metrics: "
        + ", ".join(f"{k}={v:.4f}" for k, v in calibrated_test_metrics.items())
    )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": calibrated, "feature_columns": FEATURE_COLUMNS, "model_name": best_name},
        MODELS_DIR / "win_probability.pkl",
    )

    evaluation_report = {
        "candidate_validation_metrics": results,
        "best_model": best_name,
        "raw_test_metrics": raw_test_metrics,
        "calibrated_test_metrics": calibrated_test_metrics,
        "raw_calibration_curve": compute_calibration_curve(y_test.to_numpy(), raw_test_prob),
        "calibrated_calibration_curve": compute_calibration_curve(y_test.to_numpy(), calibrated_test_prob),
    }
    with open(MODELS_DIR / "evaluation_results.json", "w") as f:
        json.dump(evaluation_report, f, indent=2)

    print(f"\nSaved calibrated model -> {MODELS_DIR / 'win_probability.pkl'}")
    print(f"Saved evaluation report -> {MODELS_DIR / 'evaluation_results.json'}")


if __name__ == "__main__":
    main()
