"""Load the trained win-probability model and score a match state.

This is the interface the Streamlit live win-probability page (Module 2)
will call: give it the current state of a run chase, get back the
batting team's win probability.

Usage:
    from src.models.predict import WinProbabilityModel
    model = WinProbabilityModel.load()
    model.predict_one(
        venue="Wankhede Stadium", batting_team="Mumbai Indians",
        bowling_team="Chennai Super Kings", over=16, ball=2, phase="death",
        target_runs=192, current_score=153, current_wickets=4,
        balls_bowled=98, balls_remaining=22, runs_required=39,
        wickets_remaining=6, current_run_rate=9.37, required_run_rate=10.64,
        last_6_runs=8, last_12_runs=14, last_18_runs=19,
        wickets_last_6=1, wickets_last_12=2,
    )
"""

from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "win_probability.pkl"


class WinProbabilityModel:
    def __init__(self, model, feature_columns: list[str], model_name: str):
        self.model = model
        self.feature_columns = feature_columns
        self.model_name = model_name

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> "WinProbabilityModel":
        bundle = joblib.load(path)
        return cls(bundle["model"], bundle["feature_columns"], bundle["model_name"])

    def predict(self, state: pd.DataFrame) -> pd.Series:
        """state: a DataFrame with one row per match state, columns matching
        the feature set the model was trained on (see FEATURE_COLUMNS in
        src/models/train.py)."""
        return pd.Series(self.model.predict_proba(state[self.feature_columns])[:, 1], index=state.index)

    def predict_one(self, **state) -> float:
        return float(self.predict(pd.DataFrame([state])).iloc[0])


if __name__ == "__main__":
    model = WinProbabilityModel.load()
    prob = model.predict_one(
        venue="Rajiv Gandhi International Stadium, Uppal, Hyderabad",
        batting_team="Royal Challengers Bengaluru",
        bowling_team="Sunrisers Hyderabad",
        over=16,
        ball=2,
        phase="death",
        target_runs=192,
        current_score=153,
        current_wickets=4,
        balls_bowled=98,
        balls_remaining=22,
        runs_required=39,
        wickets_remaining=6,
        current_run_rate=9.37,
        required_run_rate=10.64,
        last_6_runs=8,
        last_12_runs=14,
        last_18_runs=19,
        wickets_last_6=1,
        wickets_last_12=2,
    )
    print(f"Model: {model.model_name}")
    print(f"Batting team win probability: {prob:.1%}")
