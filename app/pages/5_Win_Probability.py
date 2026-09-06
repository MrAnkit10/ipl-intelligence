import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.data_loader import load_deliveries, load_matches, load_win_probability_model, team_color

FEATURES_PATH = ROOT_DIR / "data" / "features" / "win_prediction_features.parquet"

st.set_page_config(page_title="Win Probability | IPL Intelligence", page_icon="📈", layout="wide")
st.title("📈 Live Win Probability")
st.caption(
    "Replays a real historical run chase ball-by-ball through the trained, calibrated "
    "Random Forest model — Version 1 simulates live play this way rather than a paid live API "
    "(blueprint section 16)."
)


@st.cache_data
def load_features() -> pd.DataFrame:
    return pd.read_parquet(FEATURES_PATH)


features = load_features()
matches = load_matches()
deliveries = load_deliveries()
model = load_win_probability_model()

eligible_matches = matches[matches["match_id"].isin(features["match_id"])].sort_values("date", ascending=False)
eligible_matches["label"] = (
    eligible_matches["date"].dt.strftime("%Y-%m-%d")
    + " | "
    + eligible_matches["team1"]
    + " vs "
    + eligible_matches["team2"]
)

label = st.selectbox("Select a match to replay", eligible_matches["label"].tolist())
match_id = int(eligible_matches.loc[eligible_matches["label"] == label, "match_id"].iloc[0])
match_row = eligible_matches[eligible_matches["match_id"] == match_id].iloc[0]

match_features = features[features["match_id"] == match_id].sort_values("delivery_id").reset_index(drop=True)
match_features["win_prob"] = model.predict(match_features).values

match_deliveries = deliveries[deliveries["match_id"] == match_id].set_index("delivery_id")
match_features["runs_batter"] = match_deliveries.loc[match_features["delivery_id"], "runs_batter"].values
match_features["is_wicket"] = match_deliveries.loc[match_features["delivery_id"], "is_wicket"].values

batting_team = match_features["batting_team"].iloc[0]
bowling_team = match_features["bowling_team"].iloc[0]

n_balls = len(match_features)
ball_idx = st.slider("Ball", 1, n_balls, n_balls) - 1
state = match_features.iloc[ball_idx]

overs_completed = state["balls_bowled"] // 6
balls_into_over = state["balls_bowled"] % 6

st.divider()
st.subheader(f"{batting_team} vs {bowling_team}")
st.caption(f"{match_row['venue']} · {match_row['date'].strftime('%Y-%m-%d')}")

col1, col2, col3 = st.columns(3)
col1.metric("Target", int(state["target_runs"]))
col2.metric(f"{batting_team}", f"{int(state['current_score'])}/{int(state['current_wickets'])}", f"after {overs_completed}.{balls_into_over} overs")
col3.metric("Need", f"{max(int(state['runs_required']), 0)} runs off {int(state['balls_remaining'])} balls")

st.subheader("Win Probability")
batting_prob = state["win_prob"]
bowling_prob = 1 - batting_prob
bcol, wcol = st.columns(2)
with bcol:
    st.markdown(f"**{batting_team}**")
    st.progress(batting_prob)
    st.caption(f"{batting_prob:.0%}")
with wcol:
    st.markdown(f"**{bowling_team}**")
    st.progress(bowling_prob)
    st.caption(f"{bowling_prob:.0%}")

st.divider()
st.subheader("Win Probability Timeline")

x = match_features["balls_bowled"] / 6
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=x,
        y=match_features["win_prob"] * 100,
        mode="lines",
        name=f"{batting_team} win %",
        line=dict(color=team_color(batting_team), width=2),
    )
)
fig.add_hline(y=50, line_dash="dash", line_color="gray")

wickets = match_features[match_features["is_wicket"] == 1]
fig.add_trace(
    go.Scatter(
        x=wickets["balls_bowled"] / 6,
        y=wickets["win_prob"] * 100,
        mode="markers",
        name="Wicket",
        marker=dict(symbol="x", size=10, color="crimson"),
    )
)
sixes = match_features[match_features["runs_batter"] == 6]
fig.add_trace(
    go.Scatter(
        x=sixes["balls_bowled"] / 6,
        y=sixes["win_prob"] * 100,
        mode="markers",
        name="Six",
        marker=dict(symbol="star", size=10, color="green"),
    )
)
fig.add_vline(x=state["balls_bowled"] / 6, line_dash="dot", line_color="black")
fig.update_layout(
    xaxis_title="Over",
    yaxis_title=f"{batting_team} win probability (%)",
    yaxis_range=[0, 100],
    hovermode="x unified",
)
st.plotly_chart(fig, width="stretch")

st.caption(
    f"Actual result: **{match_row['winner'] or 'No result'}** "
    + (f"won by {int(match_row['win_by_runs'])} runs" if pd.notna(match_row["win_by_runs"]) else "")
    + (f"won by {int(match_row['win_by_wickets'])} wickets" if pd.notna(match_row["win_by_wickets"]) else "")
)
