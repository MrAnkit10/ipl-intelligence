"""Load the trained Player Performance Predictor and score a player/opponent/
venue combination (blueprint Module 6).

The deployed model is a Random Forest specifically so we can read each
tree's individual prediction for a given input: the spread across trees
gives an honest prediction range and P(30+)/P(50+), rather than a single
point estimate with no notion of confidence.

Usage:
    from src.models.predict_player_performance import PlayerPerformanceModel
    model = PlayerPerformanceModel.load()
    model.predict_one(
        venue="Wankhede Stadium", batting_team="Mumbai Indians",
        bowling_team="Chennai Super Kings", batting_position=3,
        career_avg_runs=38.2, career_strike_rate=132.5, last_5_avg_runs=45.0,
        last_10_avg_runs=40.1, last_5_strike_rate=140.0, season_avg_runs=41.0,
        venue_avg_runs=50.0, opponent_avg_runs=35.0,
    )
"""

from pathlib import Path

import numpy as np
import pandas as pd
import joblib

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "player_performance.pkl"


class PlayerPerformanceModel:
    def __init__(self, model, balls_model, feature_columns: list[str], model_name: str):
        self.model = model
        self.balls_model = balls_model
        self.feature_columns = feature_columns
        self.model_name = model_name

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "PlayerPerformanceModel":
        bundle = joblib.load(path)
        return cls(bundle["model"], bundle["balls_model"], bundle["feature_columns"], bundle["model_name"])

    def _tree_predictions(self, state: pd.DataFrame) -> np.ndarray:
        """One column per row, one row per tree: each tree's predicted runs."""
        preprocessor = self.model.named_steps["preprocess"]
        forest = self.model.named_steps["model"]
        X = preprocessor.transform(state[self.feature_columns])
        return np.column_stack([tree.predict(X) for tree in forest.estimators_])

    def predict(self, state: pd.DataFrame) -> pd.DataFrame:
        """Returns one row per input row: expected_runs, prediction_low/high
        (10th-90th percentile across trees), expected_strike_rate,
        probability_30_plus, probability_50_plus."""
        tree_preds = self._tree_predictions(state)
        expected_runs = tree_preds.mean(axis=1)
        expected_balls = np.clip(self.balls_model.predict(state[self.feature_columns]), 1, None)

        return pd.DataFrame(
            {
                "expected_runs": expected_runs,
                "prediction_low": np.percentile(tree_preds, 10, axis=1),
                "prediction_high": np.percentile(tree_preds, 90, axis=1),
                "expected_strike_rate": expected_runs / expected_balls * 100,
                "probability_30_plus": (tree_preds >= 30).mean(axis=1),
                "probability_50_plus": (tree_preds >= 50).mean(axis=1),
            },
            index=state.index,
        )

    def predict_one(self, **state) -> dict:
        return self.predict(pd.DataFrame([state])).iloc[0].to_dict()


if __name__ == "__main__":
    model = PlayerPerformanceModel.load()
    result = model.predict_one(
        venue="Wankhede Stadium",
        batting_team="Royal Challengers Bengaluru",
        bowling_team="Mumbai Indians",
        batting_position=3,
        career_avg_runs=38.2,
        career_strike_rate=132.5,
        last_5_avg_runs=45.0,
        last_10_avg_runs=40.1,
        last_5_strike_rate=140.0,
        season_avg_runs=41.0,
        venue_avg_runs=50.0,
        opponent_avg_runs=35.0,
    )
    print(f"Model: {model.model_name}")
    for key, value in result.items():
        print(f"{key}: {value:.1f}")
