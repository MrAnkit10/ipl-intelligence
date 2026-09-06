import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components import chart_card, inject_theme_css, render_page_title, render_stat_card
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
render_page_title("IPL Overview", "Tournament-wide numbers across every recorded season", "#004BA0")

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
            ("Highest Score", int(top_batter["highest_score"]) if pd.notna(top_batter.get("highest_score")) else "—"),
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
            ("Best Bowling", top_bowler["best_bowling_figures"] if pd.notna(top_bowler.get("best_bowling_figures")) else "—"),
            ("Economy", f"{top_bowler['economy']:.2f}"),
        ],
    )

st.divider()
with chart_card("Team Win Percentage", "All-time win % across every season played"):
    fig = px.bar(
        team_stats,
        x="team",
        y="win_pct",
        color="team",
        color_discrete_map={t: team_color(t) for t in team_stats["team"]},
        labels={"win_pct": "Win %", "team": ""},
        text="win_pct",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(showlegend=False, xaxis_tickangle=-35, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

col1, col2 = st.columns(2)
with col1:
    with chart_card("Batting First vs Chasing", "Win % by strategy, per team"):
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
            labels={"win_pct_scenario": "Win %", "team": ""},
            color_discrete_map={"Batting First": "#3B82F6", "Chasing": "#F59E0B"},
        )
        fig2.update_layout(
            xaxis_tickangle=-35, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, title=""),
        )
        st.plotly_chart(fig2, width="stretch")

with col2:
    with chart_card("Toss Impact", "How often the toss winner also wins the match"):
        toss = team_stats.dropna(subset=["toss_won_and_match_won_pct"]).sort_values(
            "toss_won_and_match_won_pct", ascending=False
        )
        fig3 = px.bar(
            toss, x="team", y="toss_won_and_match_won_pct",
            labels={"toss_won_and_match_won_pct": "Win % after winning toss", "team": ""},
            color="team", color_discrete_map={t: team_color(t) for t in toss["team"]},
        )
        fig3.update_layout(
            xaxis_tickangle=-35, showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig3, width="stretch")

st.divider()
with chart_card("Matches per Season", "Tournament size over time"):
    season_counts = matches.groupby("season_year").size().reset_index(name="matches")
    fig4 = go.Figure(
        go.Scatter(
            x=season_counts["season_year"], y=season_counts["matches"], mode="lines+markers",
            line=dict(color="#3B82F6", width=3, shape="spline"),
            marker=dict(size=8, color="#3B82F6", line=dict(color="#0A0E27", width=1.5)),
            fill="tozeroy", fillcolor="rgba(59,130,246,0.18)",
        )
    )
    fig4.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#B8C0E0"),
        xaxis=dict(title="Season", dtick=1, gridcolor="#232B55"), yaxis=dict(title="Matches", gridcolor="#232B55"),
    )
    st.plotly_chart(fig4, width="stretch")

st.divider()
lb_col1, lb_col2 = st.columns(2)
with lb_col1:
    with chart_card("Most Runs — Full Leaderboard", "Every player, ranked"):
        runs_lb = batting_stats[
            ["player_name", "current_team", "innings", "runs", "highest_score", "batting_average", "strike_rate"]
        ].copy()
        runs_lb.insert(0, "Rank", range(1, len(runs_lb) + 1))
        st.dataframe(
            runs_lb.rename(columns={
                "player_name": "Player", "current_team": "Team", "innings": "Inns",
                "runs": "Runs", "highest_score": "HS", "batting_average": "Avg", "strike_rate": "SR",
            }),
            width="stretch", hide_index=True, height=420,
        )
with lb_col2:
    with chart_card("Most Wickets — Full Leaderboard", "Every player, ranked"):
        wickets_lb = bowling_stats.sort_values("wickets", ascending=False)[
            ["player_name", "current_team", "wickets", "best_bowling_figures", "economy", "bowling_average"]
        ].copy()
        wickets_lb.insert(0, "Rank", range(1, len(wickets_lb) + 1))
        st.dataframe(
            wickets_lb.rename(columns={
                "player_name": "Player", "current_team": "Team", "wickets": "Wkts",
                "best_bowling_figures": "Best", "economy": "Econ", "bowling_average": "Avg",
            }),
            width="stretch", hide_index=True, height=420,
        )

st.divider()
with chart_card("Full Team Record"):
    st.dataframe(team_stats, width="stretch", hide_index=True)
