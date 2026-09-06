import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import chart_card, inject_theme_css, render_html, render_stat_card
from app.data_loader import (
    load_batting_stats,
    load_bowling_stats,
    load_head_to_head,
    load_player_photos,
    load_team_matches,
    load_team_stats,
    team_color,
)
from src.data.team_normalization import team_code

st.set_page_config(page_title="Team Detail | IPL Intelligence", page_icon="🏆", layout="wide")
inject_theme_css()

team_stats = load_team_stats().sort_values("team")
teams = team_stats["team"].tolist()
default_team = st.session_state.get("selected_team", "Mumbai Indians")
if default_team not in teams:
    default_team = teams[0]

team = st.selectbox("Team", teams, index=teams.index(default_team))
st.session_state["selected_team"] = team

row = team_stats[team_stats["team"] == team].iloc[0]
color = team_color(team)

render_html(
    f"""
    <div style="border-radius:16px;overflow:hidden;margin-bottom:18px;
                background:radial-gradient(circle at 15% 30%,{color}FF 0%,{color}66 60%,#0A0E27 100%);
                padding:32px;box-shadow:0 8px 24px rgba(0,0,0,0.4);">
        <div style="color:white;font-size:42px;font-weight:900;font-family:sans-serif;
                    text-shadow:0 2px 8px rgba(0,0,0,0.4);">{team_code(team)}</div>
        <div style="color:white;font-size:22px;font-weight:700;font-family:sans-serif;">{team}</div>
    </div>
    """
)

cols = st.columns(6)
cols[0].metric("Matches", int(row["matches_played"]))
cols[1].metric("Wins", int(row["wins"]))
cols[2].metric("Losses", int(row["losses"]))
cols[3].metric("Win %", f"{row['win_pct']:.0f}%" if pd.notna(row["win_pct"]) else "—")
cols[4].metric("Win % Batting First", f"{row['win_pct_batting_first']:.0f}%" if pd.notna(row["win_pct_batting_first"]) else "—")
cols[5].metric("Win % Chasing", f"{row['win_pct_chasing']:.0f}%" if pd.notna(row["win_pct_chasing"]) else "—")

st.divider()

col_h2h, col_players = st.columns([3, 2])

with col_h2h:
    with chart_card("Head-to-Head", f"{team}'s win % against every opponent it has faced"):
        h2h = load_head_to_head()
        involving = h2h[(h2h["team_a"] == team) | (h2h["team_b"] == team)].copy()
        involving["opponent"] = involving.apply(lambda r: r["team_b"] if r["team_a"] == team else r["team_a"], axis=1)
        involving["team_win_pct"] = involving.apply(
            lambda r: r["team_a_win_pct"] if r["team_a"] == team else round(100 - r["team_a_win_pct"], 2), axis=1
        )
        involving["team_wins"] = involving.apply(
            lambda r: r["team_a_wins"] if r["team_a"] == team else r["team_b_wins"], axis=1
        )
        involving = involving.sort_values("matches_played", ascending=False)
        if involving.empty:
            st.caption("No head-to-head meetings recorded.")
        else:
            fig = px.bar(
                involving, x="opponent", y="team_win_pct", text="matches_played",
                labels={"opponent": "", "team_win_pct": f"{team} win %"},
                color_discrete_sequence=[color],
            )
            fig.update_traces(texttemplate="%{text} matches", textposition="outside", marker_color=color)
            fig.add_hline(y=50, line_dash="dash", line_color="gray")
            fig.update_layout(xaxis_tickangle=-30, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")

with col_players:
    st.subheader("Key Players")
    player_photos = load_player_photos()
    batting_stats = load_batting_stats()
    bowling_stats = load_bowling_stats()

    top_batter = batting_stats[batting_stats["current_team"] == team].head(1)
    if not top_batter.empty:
        b = top_batter.iloc[0]
        render_stat_card(
            b["player_name"], "Leading Run Scorer", player_photos.get(b["player_id"]), color,
            [
                ("Runs", f"{int(b['runs']):,}"),
                ("Average", f"{b['batting_average']:.1f}" if pd.notna(b["batting_average"]) else "—"),
                ("Strike Rate", f"{b['strike_rate']:.1f}"),
                ("50s / 100s", f"{int(b['fifties'])} / {int(b['hundreds'])}"),
            ],
        )

    top_bowler = bowling_stats[bowling_stats["current_team"] == team].head(1)
    if not top_bowler.empty:
        bw = top_bowler.iloc[0]
        render_stat_card(
            bw["player_name"], "Leading Wicket Taker", player_photos.get(bw["player_id"]), color,
            [
                ("Wickets", int(bw["wickets"])),
                ("Economy", f"{bw['economy']:.2f}"),
                ("Average", f"{bw['bowling_average']:.1f}" if pd.notna(bw["bowling_average"]) else "—"),
            ],
        )

st.divider()
with chart_card("Match Log", "Every match this team has played — pick one below for its full scorecard"):
    team_matches = load_team_matches(team)
    season_filter = st.selectbox("Season", ["All"] + sorted(team_matches["season_year"].unique().tolist(), reverse=True))
    filtered = team_matches if season_filter == "All" else team_matches[team_matches["season_year"] == season_filter]
    st.dataframe(
        filtered[["date", "opponent", "venue", "result"]],
        width="stretch", hide_index=True, height=400,
    )

    filtered = filtered.copy()
    filtered["label"] = filtered["date"].astype(str) + " vs " + filtered["opponent"]
    picked = st.selectbox("Open a scorecard", filtered["label"].tolist(), key="team_match_picker")
    if st.button("Open Scorecard →", key="team_open_scorecard"):
        st.session_state["selected_match_id"] = int(filtered.loc[filtered["label"] == picked, "match_id"].iloc[0])
        st.switch_page("pages/10_Match_Detail.py")
