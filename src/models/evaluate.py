"""Shared evaluation metrics for the win-probability model (blueprint section 23)."""

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    y_pred = (y_prob >= 0.5).astype(int)
    return {
        "log_loss": log_loss(y_true, y_prob, labels=[0, 1]),
        "brier_score": brier_score_loss(y_true, y_prob),
        "roc_auc": roc_auc_score(y_true, y_prob),
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": root_mean_squared_error(y_true, y_pred),
        "r2": r2_score(y_true, y_pred),
    }


def compute_calibration_curve(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> dict:
    observed, predicted = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="quantile")
    return {"predicted_probability": predicted.tolist(), "observed_frequency": observed.tolist()}
