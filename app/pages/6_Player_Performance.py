import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components import avatar_html, chart_card, inject_theme_css, render_html, render_page_title
from app.data_loader import load_batting_innings_table, load_player_performance_model, load_player_photos, team_color
from src.data.team_normalization import canonical_team_name

st.set_page_config(page_title="Player Performance Predictor | IPL Intelligence", page_icon="🔮", layout="wide")
inject_theme_css()
render_page_title(
    "Player Performance Predictor",
    "Estimates expected runs for a player's next innings from career form, recent form, "
    "season form, and venue/opponent history (blueprint Module 6).",
    "#3A225D",
)

MIN_PRIOR_INNINGS = 3

innings = load_batting_innings_table()
model = load_player_performance_model()
player_photos = load_player_photos()

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

color = team_color(current_team)
photo = avatar_html(player_name, player_photos.get(player_id), size=88)
render_html(
    f"""
    <div style="border-radius:16px;overflow:hidden;margin-bottom:18px;display:flex;align-items:center;gap:18px;
                background:linear-gradient(90deg,{color}55 0%,#131A3A 60%);border:1px solid {color}88;
                padding:20px 24px;">
        {photo}
        <div style="color:white;font-family:sans-serif;flex:1;">
            <div style="font-size:22px;font-weight:800;">{player_name}</div>
            <div style="color:#B8C0E0;font-size:13px;">{current_team}</div>
        </div>
        <div style="color:white;opacity:0.6;font-weight:700;font-family:sans-serif;padding:0 12px;">vs</div>
        <div style="color:white;font-family:sans-serif;text-align:right;">
            <div style="font-size:18px;font-weight:800;">{opponent_team}</div>
            <div style="color:#B8C0E0;font-size:13px;">{venue}</div>
        </div>
    </div>
    """
)

gauge_col, prob_col, form_col = st.columns([1, 1, 2])

with gauge_col:
    with chart_card("Expected Runs", "Predicted mean and 10th-90th percentile range"):
        fig_gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=prediction["expected_runs"],
                number={"suffix": " runs", "font": {"color": "white", "size": 36}},
                gauge={
                    "axis": {"range": [0, max(120, prediction["prediction_high"] + 10)], "tickcolor": "#B8C0E0"},
                    "bar": {"color": color},
                    "steps": [
                        {"range": [prediction["prediction_low"], prediction["prediction_high"]], "color": f"{color}33"},
                    ],
                    "threshold": {
                        "line": {"color": "white", "width": 2},
                        "value": prediction["expected_runs"],
                    },
                },
            )
        )
        fig_gauge.update_layout(
            height=220, margin=dict(l=20, r=20, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", font={"color": "#B8C0E0"},
        )
        st.plotly_chart(fig_gauge, width="stretch")
        st.caption(f"Range: {prediction['prediction_low']:.0f}–{prediction['prediction_high']:.0f} runs · Expected SR {prediction['expected_strike_rate']:.0f}")

with prob_col:
    with chart_card("Milestone Probability", "Share of the model's trees predicting this score or higher"):
        st.markdown(f"**30+ runs**")
        st.progress(min(prediction["probability_30_plus"], 1.0))
        st.caption(f"{prediction['probability_30_plus']:.0%}")
        st.markdown(f"**50+ runs**")
        st.progress(min(prediction["probability_50_plus"], 1.0))
        st.caption(f"{prediction['probability_50_plus']:.0%}")

with form_col:
    with chart_card("Form Comparison", "Average runs across different windows, feeding the prediction above"):
        form_df = pd.DataFrame(
            {
                "window": ["Career", "Last 10", "Last 5", "This Season", f"vs {opponent_team}", f"at {venue}"],
                "avg_runs": [
                    state["career_avg_runs"], state["last_10_avg_runs"], state["last_5_avg_runs"],
                    state["season_avg_runs"], state["opponent_avg_runs"], state["venue_avg_runs"],
                ],
            }
        )
        fig_form = px.bar(form_df, x="avg_runs", y="window", orientation="h", text="avg_runs", color_discrete_sequence=[color])
        fig_form.update_traces(texttemplate="%{text:.1f}", textposition="outside", marker_color=color)
        fig_form.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Average runs", yaxis_title="", font={"color": "#B8C0E0"},
        )
        st.plotly_chart(fig_form, width="stretch")

st.caption(
    "Honest limitation: on held-out 2025-2026 seasons this model's MAE is within about "
    "1.5% of simply predicting a player's career average — single T20 innings scores are "
    "close to random around a player's mean. See the Model Insights page for the full "
    "validation/test comparison against that naive baseline."
)
