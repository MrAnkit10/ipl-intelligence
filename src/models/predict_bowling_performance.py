"""Load the trained Bowling Performance Predictor and score a
bowler/opponent/venue combination — bowling-side counterpart to
predict_player_performance.py.

The deployed model is a Random Forest specifically so we can read each
tree's individual prediction for a given input: the spread across trees
gives an honest prediction range and P(2+)/P(3+) wickets, rather than a
single point estimate with no notion of confidence.

Usage:
    from src.models.predict_bowling_performance import BowlingPerformanceModel
    model = BowlingPerformanceModel.load()
    model.predict_one(
        venue="Wankhede Stadium, Mumbai", bowling_team="Mumbai Indians",
        batting_team="Chennai Super Kings", career_avg_wickets=1.2,
        career_economy=7.8, last_5_avg_wickets=1.4, last_10_avg_wickets=1.3,
        last_5_economy=7.5, season_avg_wickets=1.5, venue_avg_wickets=1.1,
        opponent_avg_wickets=1.3,
    )
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "bowling_performance.pkl"


class BowlingPerformanceModel:
    def __init__(self, model, economy_model, feature_columns: list[str], model_name: str):
        self.model = model
        self.economy_model = economy_model
        self.feature_columns = feature_columns
        self.model_name = model_name

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "BowlingPerformanceModel":
        bundle = joblib.load(path)
        return cls(bundle["model"], bundle["economy_model"], bundle["feature_columns"], bundle["model_name"])

    def _tree_predictions(self, state: pd.DataFrame) -> np.ndarray:
        """One column per row, one row per tree: each tree's predicted wickets."""
        preprocessor = self.model.named_steps["preprocess"]
        forest = self.model.named_steps["model"]
        X = preprocessor.transform(state[self.feature_columns])
        return np.column_stack([tree.predict(X) for tree in forest.estimators_])

    def predict(self, state: pd.DataFrame) -> pd.DataFrame:
        """Returns one row per input row: expected_wickets, prediction_low/high
        (10th-90th percentile across trees), expected_economy,
        probability_2_plus, probability_3_plus."""
        tree_preds = self._tree_predictions(state)
        expected_wickets = tree_preds.mean(axis=1)
        expected_economy = self.economy_model.predict(state[self.feature_columns])

        return pd.DataFrame(
            {
                "expected_wickets": expected_wickets,
                "prediction_low": np.percentile(tree_preds, 10, axis=1),
                "prediction_high": np.percentile(tree_preds, 90, axis=1),
                "expected_economy": expected_economy,
                "probability_2_plus": (tree_preds >= 2).mean(axis=1),
                "probability_3_plus": (tree_preds >= 3).mean(axis=1),
            },
            index=state.index,
        )

    def predict_one(self, **state) -> dict:
        return self.predict(pd.DataFrame([state])).iloc[0].to_dict()


if __name__ == "__main__":
    model = BowlingPerformanceModel.load()
    result = model.predict_one(
        venue="Wankhede Stadium, Mumbai",
        bowling_team="Mumbai Indians",
        batting_team="Chennai Super Kings",
        career_avg_wickets=1.2,
        career_economy=7.8,
        last_5_avg_wickets=1.4,
        last_10_avg_wickets=1.3,
        last_5_economy=7.5,
        season_avg_wickets=1.5,
        venue_avg_wickets=1.1,
        opponent_avg_wickets=1.3,
    )
    print(f"Model: {model.model_name}")
    for key, value in result.items():
        print(f"{key}: {value:.2f}")
