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
from app.data_loader import (
    load_batting_innings_table,
    load_batting_stats,
    load_bowling_matches_table,
    load_bowling_performance_model,
    load_bowling_stats,
    load_player_performance_model,
    load_player_photos,
    team_color,
)

st.set_page_config(page_title="Player Performance Predictor | IPL Intelligence", page_icon="🔮", layout="wide")
inject_theme_css()
render_page_title(
    "Player Performance Predictor",
    "Estimates a player's next match, batting and/or bowling as applicable, from career "
    "form, recent form, season form, and venue/opponent history (blueprint Module 6).",
    "#3A225D",
)

MIN_PRIOR_INNINGS = 3
MIN_PRIOR_MATCHES = 3

innings = load_batting_innings_table()
bowling_matches = load_bowling_matches_table()
bat_model = load_player_performance_model()
bowl_model = load_bowling_performance_model()
player_photos = load_player_photos()

bat_innings_count = innings.groupby("player_id").size()
bat_eligible_ids = set(bat_innings_count[bat_innings_count >= MIN_PRIOR_INNINGS].index)

bowl_matches_count = bowling_matches.groupby("player_id").size()
bowl_eligible_ids = set(bowl_matches_count[bowl_matches_count >= MIN_PRIOR_MATCHES].index)

bat_names = innings[innings["player_id"].isin(bat_eligible_ids)][["player_id", "player_name"]]
bowl_names = bowling_matches[bowling_matches["player_id"].isin(bowl_eligible_ids)][["player_id", "player_name"]]
player_names = pd.concat([bat_names, bowl_names]).drop_duplicates().sort_values("player_name")

all_names = player_names["player_name"].tolist()
col1, col2, col3 = st.columns(3)
player_name = col1.selectbox(
    "Player", all_names,
    index=all_names.index("V Kohli") if "V Kohli" in all_names else 0,
)
player_id = player_names.loc[player_names["player_name"] == player_name, "player_id"].iloc[0]

has_bat = player_id in bat_eligible_ids
has_bowl = player_id in bowl_eligible_ids

player_innings = innings[innings["player_id"] == player_id].sort_values("date") if has_bat else innings.iloc[0:0]
player_bowl_matches = (
    bowling_matches[bowling_matches["player_id"] == player_id].sort_values("date") if has_bowl else bowling_matches.iloc[0:0]
)

# Which section(s) to show is a role question, not just "is there enough
# history to compute a number" — a specialist bowler can rack up 20+
# tailend batting innings while averaging single digits (Bumrah: 29
# innings, 75 career runs), which would wrongly earn a "Batting
# Prediction" section without this check. Career runs/wickets (not raw
# innings count) is what actually distinguishes a real batting/bowling
# threat, matching the same significance rule Player Analytics uses.
batting_stats, bowling_stats_table = load_batting_stats(), load_bowling_stats()
bat_stats_row = batting_stats[batting_stats["player_id"] == player_id]
bowl_stats_row = bowling_stats_table[bowling_stats_table["player_id"] == player_id]
bat_significant = has_bat and not bat_stats_row.empty and bat_stats_row.iloc[0]["runs"] >= 500
bowl_significant = has_bowl and not bowl_stats_row.empty and bowl_stats_row.iloc[0]["wickets"] >= 20

if bat_significant and bowl_significant:
    role, show_bat, show_bowl = "All-rounder", True, True
elif bat_significant:
    role, show_bat, show_bowl = "Batter", True, False
elif bowl_significant:
    role, show_bat, show_bowl = "Bowler", False, True
else:
    # Below both significance bars (a fringe player) - fall back to
    # whichever side has real history rather than showing nothing.
    role = "All-rounder" if has_bat and has_bowl else ("Batter" if has_bat else "Bowler")
    show_bat, show_bowl = has_bat, has_bowl

current_team = (
    player_innings["batting_team"].iloc[-1] if has_bat else player_bowl_matches["bowling_team"].iloc[-1]
)

all_teams = sorted(
    set(innings["batting_team"]) | set(innings["bowling_team"])
    | set(bowling_matches["bowling_team"]) | set(bowling_matches["batting_team"])
)
opponent_options = [t for t in all_teams if t != current_team]
opponent_team = col2.selectbox("Opponent", opponent_options)

venues = sorted(set(innings["venue"]) | set(bowling_matches["venue"]))
venue = col3.selectbox("Venue", venues)

color = team_color(current_team)
photo = avatar_html(player_name, player_photos.get(player_id), size=88)
render_html(
    f"""
    <div style="border-radius:16px;overflow:hidden;margin-bottom:8px;display:flex;align-items:center;gap:18px;
                background:linear-gradient(90deg,{color}55 0%,#131A3A 60%);border:1px solid {color}88;
                padding:20px 24px;">
        {photo}
        <div style="color:white;font-family:sans-serif;flex:1;">
            <div style="font-size:22px;font-weight:800;">{player_name}</div>
            <div style="color:#B8C0E0;font-size:13px;">{current_team}</div>
        </div>
        <span style="color:white;background:{color};padding:3px 12px;border-radius:20px;
                    font-size:12px;font-weight:800;font-family:sans-serif;letter-spacing:0.02em;
                    align-self:flex-start;margin-top:4px;">{role.upper()}</span>
        <div style="color:white;opacity:0.6;font-weight:700;font-family:sans-serif;padding:0 12px;">vs</div>
        <div style="color:white;font-family:sans-serif;text-align:right;">
            <div style="font-size:18px;font-weight:800;">{opponent_team}</div>
            <div style="color:#B8C0E0;font-size:13px;">{venue}</div>
        </div>
    </div>
    """
)
st.caption("Role and eligibility are based on real career history (3+ prior innings/matches) — never assumed.")


def compute_batting_state(player_innings: pd.DataFrame, opponent_team: str, venue: str) -> dict:
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


def compute_bowling_state(player_matches: pd.DataFrame, opponent_team: str, venue: str) -> dict:
    career_avg_wickets = player_matches["wickets"].mean()
    total_runs, total_balls = player_matches["runs_conceded"].sum(), player_matches["balls_bowled"].sum()
    career_economy = total_runs / total_balls * 6 if total_balls > 0 else np.nan

    last5 = player_matches.tail(5)
    last_5_avg_wickets = last5["wickets"].mean()
    last5_balls = last5["balls_bowled"].sum()
    last_5_economy = last5["runs_conceded"].sum() / last5_balls * 6 if last5_balls > 0 else np.nan

    last_10_avg_wickets = player_matches.tail(10)["wickets"].mean()

    current_season = player_matches["season_year"].max()
    season_rows = player_matches[player_matches["season_year"] == current_season]
    season_avg_wickets = season_rows["wickets"].mean() if len(season_rows) else career_avg_wickets

    venue_rows = player_matches[player_matches["venue"] == venue]
    venue_avg_wickets = venue_rows["wickets"].mean() if len(venue_rows) else career_avg_wickets

    opponent_rows = player_matches[player_matches["batting_team"] == opponent_team]
    opponent_avg_wickets = opponent_rows["wickets"].mean() if len(opponent_rows) else career_avg_wickets

    return {
        "venue": venue,
        "bowling_team": player_matches["bowling_team"].iloc[-1],
        "batting_team": opponent_team,
        "career_avg_wickets": career_avg_wickets,
        "career_economy": career_economy,
        "last_5_avg_wickets": last_5_avg_wickets,
        "last_10_avg_wickets": last_10_avg_wickets,
        "last_5_economy": last_5_economy,
        "season_avg_wickets": season_avg_wickets,
        "venue_avg_wickets": venue_avg_wickets,
        "opponent_avg_wickets": opponent_avg_wickets,
    }


if show_bat:
    st.divider()
    st.subheader("Batting Prediction")
    bat_state = compute_batting_state(player_innings, opponent_team, venue)
    bat_pred = bat_model.predict_one(**bat_state)

    gauge_col, prob_col, form_col = st.columns([1, 1, 2])
    with gauge_col:
        with chart_card("Expected Runs", "Predicted mean and 10th-90th percentile range"):
            fig_gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=bat_pred["expected_runs"],
                    number={"suffix": " runs", "font": {"color": "white", "size": 36}},
                    gauge={
                        "axis": {"range": [0, max(120, bat_pred["prediction_high"] + 10)], "tickcolor": "#B8C0E0"},
                        "bar": {"color": color},
                        "steps": [
                            {"range": [bat_pred["prediction_low"], bat_pred["prediction_high"]], "color": f"{color}33"},
                        ],
                        "threshold": {"line": {"color": "white", "width": 2}, "value": bat_pred["expected_runs"]},
                    },
                )
            )
            fig_gauge.update_layout(
                height=220, margin=dict(l=20, r=20, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)", font={"color": "#B8C0E0"},
            )
            st.plotly_chart(fig_gauge, width="stretch")
            st.caption(
                f"Range: {bat_pred['prediction_low']:.0f}–{bat_pred['prediction_high']:.0f} runs · "
                f"Expected SR {bat_pred['expected_strike_rate']:.0f}"
            )

    with prob_col:
        with chart_card("Milestone Probability", "Share of the model's trees predicting this score or higher"):
            st.markdown("**30+ runs**")
            st.progress(min(bat_pred["probability_30_plus"], 1.0))
            st.caption(f"{bat_pred['probability_30_plus']:.0%}")
            st.markdown("**50+ runs**")
            st.progress(min(bat_pred["probability_50_plus"], 1.0))
            st.caption(f"{bat_pred['probability_50_plus']:.0%}")

    with form_col:
        with chart_card("Form Comparison", "Average runs across different windows, feeding the prediction above"):
            form_df = pd.DataFrame(
                {
                    "window": ["Career", "Last 10", "Last 5", "This Season", f"vs {opponent_team}", f"at {venue}"],
                    "avg_runs": [
                        bat_state["career_avg_runs"], bat_state["last_10_avg_runs"], bat_state["last_5_avg_runs"],
                        bat_state["season_avg_runs"], bat_state["opponent_avg_runs"], bat_state["venue_avg_runs"],
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
        "1.9% of simply predicting a player's career average — single T20 innings scores are "
        "close to random around a player's mean. See the Model Insights page for the full "
        "validation/test comparison against that naive baseline."
    )

if show_bowl:
    st.divider()
    st.subheader("Bowling Prediction")
    bowl_state = compute_bowling_state(player_bowl_matches, opponent_team, venue)
    bowl_pred = bowl_model.predict_one(**bowl_state)

    gauge_col, prob_col, form_col = st.columns([1, 1, 2])
    with gauge_col:
        with chart_card("Expected Wickets", "Predicted mean and 10th-90th percentile range"):
            fig_gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=bowl_pred["expected_wickets"],
                    number={"suffix": " wkts", "font": {"color": "white", "size": 36}},
                    gauge={
                        "axis": {"range": [0, max(4, bowl_pred["prediction_high"] + 1)], "tickcolor": "#B8C0E0"},
                        "bar": {"color": color},
                        "steps": [
                            {"range": [bowl_pred["prediction_low"], bowl_pred["prediction_high"]], "color": f"{color}33"},
                        ],
                        "threshold": {"line": {"color": "white", "width": 2}, "value": bowl_pred["expected_wickets"]},
                    },
                )
            )
            fig_gauge.update_layout(
                height=220, margin=dict(l=20, r=20, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)", font={"color": "#B8C0E0"},
            )
            st.plotly_chart(fig_gauge, width="stretch")
            st.caption(
                f"Range: {bowl_pred['prediction_low']:.1f}–{bowl_pred['prediction_high']:.1f} wkts · "
                f"Expected economy {bowl_pred['expected_economy']:.1f}"
            )

    with prob_col:
        with chart_card("Milestone Probability", "Share of the model's trees predicting this many wickets or more"):
            st.markdown("**2+ wickets**")
            st.progress(min(bowl_pred["probability_2_plus"], 1.0))
            st.caption(f"{bowl_pred['probability_2_plus']:.0%}")
            st.markdown("**3+ wickets**")
            st.progress(min(bowl_pred["probability_3_plus"], 1.0))
            st.caption(f"{bowl_pred['probability_3_plus']:.0%}")

    with form_col:
        with chart_card("Form Comparison", "Average wickets across different windows, feeding the prediction above"):
            form_df = pd.DataFrame(
                {
                    "window": ["Career", "Last 10", "Last 5", "This Season", f"vs {opponent_team}", f"at {venue}"],
                    "avg_wickets": [
                        bowl_state["career_avg_wickets"], bowl_state["last_10_avg_wickets"], bowl_state["last_5_avg_wickets"],
                        bowl_state["season_avg_wickets"], bowl_state["opponent_avg_wickets"], bowl_state["venue_avg_wickets"],
                    ],
                }
            )
            fig_form = px.bar(form_df, x="avg_wickets", y="window", orientation="h", text="avg_wickets", color_discrete_sequence=[color])
            fig_form.update_traces(texttemplate="%{text:.2f}", textposition="outside", marker_color=color)
            fig_form.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Average wickets", yaxis_title="", font={"color": "#B8C0E0"},
            )
            st.plotly_chart(fig_form, width="stretch")

    st.caption(
        "Honest limitation: wickets in a single T20 match are low-count and high-variance "
        "(most bowlers take 0-2), so this model's edge over a naive career-average baseline "
        "is modest — see the Model Insights page for the full validation/test comparison."
    )
