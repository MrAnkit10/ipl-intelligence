import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import inject_theme_css, render_stat_card
from app.data_loader import (
    load_batting_stats,
    load_bowling_stats,
    load_deliveries,
    load_matches,
    load_player_photos,
    load_team_stats,
    team_color,
)
from src.analytics.overview import compute_overview

st.set_page_config(page_title="IPL Overview | IPL Intelligence", page_icon="📊", layout="wide")
inject_theme_css()
st.title("📊 IPL Overview")

matches = load_matches()
deliveries = load_deliveries()
team_stats = load_team_stats().sort_values("win_pct", ascending=False)
batting_stats = load_batting_stats()
bowling_stats = load_bowling_stats()
player_photos = load_player_photos()
overview = compute_overview(matches, deliveries, batting_stats, bowling_stats)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Matches", f"{overview['matches_played']:,}")
col2.metric("Total Runs", f"{overview['total_runs']:,}")
col3.metric("Total Wickets", f"{overview['total_wickets']:,}")
col4.metric("Sixes", f"{overview['total_sixes']:,}")

st.subheader("Tournament Leaders")
lead_col1, lead_col2 = st.columns(2)
with lead_col1:
    top_batter = batting_stats.iloc[0]
    render_stat_card(
        top_batter["player_name"], "Leading Run Scorer", player_photos.get(top_batter["player_id"]),
        team_color(top_batter.get("current_team", "")),
        [
            ("Runs", f"{int(top_batter['runs']):,}"),
            ("Average", f"{top_batter['batting_average']:.1f}" if pd.notna(top_batter["batting_average"]) else "—"),
            ("Strike Rate", f"{top_batter['strike_rate']:.1f}"),
        ],
    )
with lead_col2:
    top_bowler = bowling_stats.iloc[0]
    render_stat_card(
        top_bowler["player_name"], "Leading Wicket Taker", player_photos.get(top_bowler["player_id"]),
        team_color(top_bowler.get("current_team", "")),
        [
            ("Wickets", int(top_bowler["wickets"])),
            ("Economy", f"{top_bowler['economy']:.2f}"),
        ],
    )

st.divider()
st.subheader("Team Win Percentage")
fig = px.bar(
    team_stats,
    x="team",
    y="win_pct",
    color="team",
    color_discrete_map={t: team_color(t) for t in team_stats["team"]},
    labels={"win_pct": "Win %", "team": "Team"},
    text="win_pct",
)
fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig.update_layout(showlegend=False, xaxis_tickangle=-35)
st.plotly_chart(fig, width="stretch")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Batting First vs Chasing")
    melted = team_stats.melt(
        id_vars="team",
        value_vars=["win_pct_batting_first", "win_pct_chasing"],
        var_name="scenario",
        value_name="win_pct_scenario",
    )
    melted["scenario"] = melted["scenario"].map(
        {"win_pct_batting_first": "Batting First", "win_pct_chasing": "Chasing"}
    )
    fig2 = px.bar(
        melted, x="team", y="win_pct_scenario", color="scenario", barmode="group",
        labels={"win_pct_scenario": "Win %", "team": "Team"},
    )
    fig2.update_layout(xaxis_tickangle=-35)
    st.plotly_chart(fig2, width="stretch")

with col2:
    st.subheader("Toss Impact")
    toss = team_stats.dropna(subset=["toss_won_and_match_won_pct"]).sort_values(
        "toss_won_and_match_won_pct", ascending=False
    )
    fig3 = px.bar(
        toss, x="team", y="toss_won_and_match_won_pct",
        labels={"toss_won_and_match_won_pct": "Win % after winning toss", "team": "Team"},
    )
    fig3.update_layout(xaxis_tickangle=-35)
    st.plotly_chart(fig3, width="stretch")

st.divider()
st.subheader("Matches per Season")
season_counts = matches.groupby("season_year").size().reset_index(name="matches")
fig4 = px.bar(season_counts, x="season_year", y="matches", labels={"season_year": "Season", "matches": "Matches"})
st.plotly_chart(fig4, width="stretch")

st.divider()
st.subheader("Full Team Record")
st.dataframe(team_stats, width="stretch", hide_index=True)
