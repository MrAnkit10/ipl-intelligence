import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd
import streamlit as st

from app.data_loader import load_batting_innings_table, load_player_performance_model
from src.data.team_normalization import canonical_team_name

st.set_page_config(page_title="Player Performance Predictor | IPL Intelligence", page_icon="🔮", layout="wide")
st.title("🔮 Player Performance Predictor")
st.caption(
    "Given a player, an opponent, and a venue, estimates expected runs for their next "
    "innings from career form, recent form, season form, and venue/opponent history "
    "(blueprint Module 6)."
)

MIN_PRIOR_INNINGS = 3

innings = load_batting_innings_table()
model = load_player_performance_model()

innings_count = innings.groupby("player_id").size()
eligible_players = innings_count[innings_count >= MIN_PRIOR_INNINGS].index
player_names = (
    innings[innings["player_id"].isin(eligible_players)][["player_id", "player_name"]]
    .drop_duplicates()
    .sort_values("player_name")
)

col1, col2, col3 = st.columns(3)
player_name = col1.selectbox(
    "Player", player_names["player_name"].tolist(),
    index=player_names["player_name"].tolist().index("V Kohli") if "V Kohli" in player_names["player_name"].tolist() else 0,
)
player_id = player_names.loc[player_names["player_name"] == player_name, "player_id"].iloc[0]
player_innings = innings[innings["player_id"] == player_id].sort_values("date")

all_teams = sorted(set(innings["batting_team"]) | set(innings["bowling_team"]))
current_team = player_innings["batting_team"].iloc[-1]
opponent_options = [t for t in all_teams if t != current_team]
opponent_team = col2.selectbox("Opponent", opponent_options)

venues = sorted(innings["venue"].unique())
venue = col3.selectbox("Venue", venues)

st.divider()


def compute_current_state(player_innings: pd.DataFrame, opponent_team: str, venue: str) -> dict:
    career_avg_runs = player_innings["runs"].mean()
    total_runs, total_balls = player_innings["runs"].sum(), player_innings["balls_faced"].sum()
    career_strike_rate = total_runs / total_balls * 100 if total_balls > 0 else np.nan

    last5 = player_innings.tail(5)
    last_5_avg_runs = last5["runs"].mean()
    last5_balls = last5["balls_faced"].sum()
    last_5_strike_rate = last5["runs"].sum() / last5_balls * 100 if last5_balls > 0 else np.nan

    last_10_avg_runs = player_innings.tail(10)["runs"].mean()

    current_season = player_innings["season_year"].max()
    season_rows = player_innings[player_innings["season_year"] == current_season]
    season_avg_runs = season_rows["runs"].mean() if len(season_rows) else career_avg_runs

    venue_rows = player_innings[player_innings["venue"] == venue]
    venue_avg_runs = venue_rows["runs"].mean() if len(venue_rows) else career_avg_runs

    opponent_rows = player_innings[player_innings["bowling_team"] == opponent_team]
    opponent_avg_runs = opponent_rows["runs"].mean() if len(opponent_rows) else career_avg_runs

    batting_position = player_innings["batting_position"].tail(5).median()

    return {
        "venue": venue,
        "batting_team": player_innings["batting_team"].iloc[-1],
        "bowling_team": opponent_team,
        "batting_position": batting_position,
        "career_avg_runs": career_avg_runs,
        "career_strike_rate": career_strike_rate,
        "last_5_avg_runs": last_5_avg_runs,
        "last_10_avg_runs": last_10_avg_runs,
        "last_5_strike_rate": last_5_strike_rate,
        "season_avg_runs": season_avg_runs,
        "venue_avg_runs": venue_avg_runs,
        "opponent_avg_runs": opponent_avg_runs,
    }


state = compute_current_state(player_innings, opponent_team, venue)
prediction = model.predict_one(**state)

st.subheader(f"{player_name} vs {opponent_team} at {venue}")
cols = st.columns(4)
cols[0].metric("Expected Runs", f"{prediction['expected_runs']:.1f}")
cols[1].metric("Prediction Range", f"{prediction['prediction_low']:.0f}–{prediction['prediction_high']:.0f}")
cols[2].metric("Expected Strike Rate", f"{prediction['expected_strike_rate']:.0f}")
cols[3].metric("Probability 30+ / 50+", f"{prediction['probability_30_plus']:.0%} / {prediction['probability_50_plus']:.0%}")

with st.expander("Form inputs used for this prediction"):
    st.json(
        {
            "career_average": round(state["career_avg_runs"], 1),
            "career_strike_rate": round(state["career_strike_rate"], 1) if pd.notna(state["career_strike_rate"]) else None,
            "last_5_innings_average": round(state["last_5_avg_runs"], 1),
            "last_10_innings_average": round(state["last_10_avg_runs"], 1),
            "season_average_this_year": round(state["season_avg_runs"], 1),
            f"average_at_{venue}": round(state["venue_avg_runs"], 1),
            f"average_vs_{opponent_team}": round(state["opponent_avg_runs"], 1),
            "innings_played": len(player_innings),
        }
    )

st.caption(
    "Honest limitation: on held-out 2025-2026 seasons this model's MAE is within about "
    "1.5% of simply predicting a player's career average — single T20 innings scores are "
    "close to random around a player's mean. See the Model Insights page for the full "
    "validation/test comparison against that naive baseline."
)
