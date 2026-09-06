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


@st.cache_resource
def load_win_probability_model():
    from src.models.predict import WinProbabilityModel

    return WinProbabilityModel.load()


@st.cache_data
def load_evaluation_report() -> dict:
    import json

    path = MODELS_DIR / "evaluation_results.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def team_color(team: str) -> str:
    return TEAM_COLORS.get(team, "#888888")
