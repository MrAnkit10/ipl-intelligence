"""Cached data access for the Streamlit app.

Every page reads through here so the underlying Parquet/CSV files and the
trained model are loaded from disk exactly once per server process.
"""

from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"

TEAM_COLORS = {
    "Royal Challengers Bengaluru": "#EC1C24",
    "Mumbai Indians": "#004BA0",
    "Chennai Super Kings": "#FDB913",
    "Kolkata Knight Riders": "#3A225D",
    "Rajasthan Royals": "#EA1A85",
    "Delhi Capitals": "#17479E",
    "Sunrisers Hyderabad": "#FF822A",
    "Punjab Kings": "#ED1B24",
    "Gujarat Titans": "#1B2133",
    "Lucknow Super Giants": "#A72056",
    "Deccan Chargers": "#0D3692",
    "Gujarat Lions": "#E04F16",
    "Pune Warriors": "#6A3E11",
    "Rising Pune Supergiant": "#B03060",
    "Kochi Tuskers Kerala": "#F58220",
}


@st.cache_data
def load_matches() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / "matches.parquet")


@st.cache_data
def load_deliveries() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / "deliveries.parquet")


@st.cache_data
def load_players() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / "players.parquet")


@st.cache_data
def load_batting_stats() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "batting_stats.csv")


@st.cache_data
def load_bowling_stats() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "bowling_stats.csv")


@st.cache_data
def load_team_stats() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "team_stats.csv")


@st.cache_data
def load_venue_stats() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "venue_stats.csv")


@st.cache_data
def load_head_to_head() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "head_to_head.csv")


@st.cache_data
def load_team_matches(team: str) -> pd.DataFrame:
    """Every match a canonical team played, newest first, with the
    opponent, result, and margin resolved from the batting team's
    perspective."""
    from src.data.team_normalization import canonical_team_name

    matches = load_matches().copy()
    for col in ["team1", "team2", "toss_winner", "winner"]:
        matches[col] = matches[col].map(canonical_team_name, na_action="ignore")

    played = matches[(matches["team1"] == team) | (matches["team2"] == team)].copy()
    played["opponent"] = played.apply(lambda r: r["team2"] if r["team1"] == team else r["team1"], axis=1)

    def _result(row) -> str:
        if row["outcome_type"] != "win":
            return "No result"
        if row["winner"] == team:
            margin = f"by {int(row['win_by_runs'])} runs" if pd.notna(row["win_by_runs"]) else f"by {int(row['win_by_wickets'])} wkts"
            return f"Won {margin}"
        margin = f"by {int(row['win_by_runs'])} runs" if pd.notna(row["win_by_runs"]) else f"by {int(row['win_by_wickets'])} wkts"
        return f"Lost {margin}"

    played["result"] = played.apply(_result, axis=1)
    return played.sort_values("date", ascending=False)[
        ["match_id", "date", "opponent", "venue", "result", "season_year"]
    ].reset_index(drop=True)


@st.cache_data
def load_player_photos() -> dict:
    """player_id -> photo_url, only for players a real photo was found for."""
    path = PROCESSED_DIR / "player_photos.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path).dropna(subset=["photo_url"])
    return dict(zip(df["player_id"], df["photo_url"]))


@st.cache_data
def load_venue_photos() -> dict:
    """venue -> photo_url, only for venues a real photo was found for."""
    path = PROCESSED_DIR / "venue_photos.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path).dropna(subset=["photo_url"])
    return dict(zip(df["venue"], df["photo_url"]))


@st.cache_data
def load_dismissal_breakdown() -> pd.DataFrame:
    path = PROCESSED_DIR / "dismissal_breakdown.csv"
    if not path.exists():
        return pd.DataFrame(columns=["player_id", "dismissal_kind", "count"])
    return pd.read_csv(path)


@st.cache_resource
def load_win_probability_model():
    from src.models.predict import WinProbabilityModel

    return WinProbabilityModel.load()


@st.cache_resource
def load_player_performance_model():
    from src.models.predict_player_performance import PlayerPerformanceModel

    return PlayerPerformanceModel.load()


@st.cache_data
def load_batting_innings_table() -> pd.DataFrame:
    from src.features.build_player_performance_features import build_batting_innings

    return build_batting_innings(load_matches(), load_deliveries())


@st.cache_data
def load_evaluation_report() -> dict:
    import json

    path = MODELS_DIR / "evaluation_results.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


@st.cache_data
def load_player_performance_evaluation_report() -> dict:
    import json

    path = MODELS_DIR / "player_performance_evaluation.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def team_color(team: str) -> str:
    return TEAM_COLORS.get(team, "#888888")
