import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from app.components import BALL_ICON_SVG, avatar_html, inject_theme_css, render_html
from app.data_loader import (
    load_batting_stats,
    load_bowling_stats,
    load_deliveries,
    load_matches,
    load_player_photos,
    team_color,
)
from src.analytics.overview import compute_overview

st.set_page_config(page_title="IPL Intelligence", page_icon="🏏", layout="wide")
inject_theme_css()

matches = load_matches()
deliveries = load_deliveries()
batting_stats = load_batting_stats()
bowling_stats = load_bowling_stats()
overview = compute_overview(matches, deliveries, batting_stats, bowling_stats)

ball = BALL_ICON_SVG.format(size=56, color="#ffffffAA")
render_html(
    f"""
    <div style="border-radius:18px;overflow:hidden;margin-bottom:20px;padding:36px 32px;
                background:radial-gradient(circle at 10% 20%,#EC1C24 0%,#131A3A 45%,#0A0E27 100%);
                box-shadow:0 10px 28px rgba(0,0,0,0.4);display:flex;align-items:center;gap:16px;">
        {ball}
        <div>
            <div style="color:white;font-size:38px;font-weight:900;font-family:sans-serif;">IPL Intelligence</div>
            <div style="color:#DDE3FF;font-size:15px;font-family:sans-serif;margin-top:4px;">
                Cricket Analytics &amp; Win Prediction Platform — 19 seasons of IPL ball-by-ball data
            </div>
        </div>
    </div>
    """
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Seasons", overview["seasons"])
col2.metric("Matches Analysed", f"{overview['matches_played']:,}")
col3.metric("Balls Analysed", f"{len(deliveries):,}")
col4.metric("Players", f"{deliveries['batter_id'].nunique():,}")

st.divider()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Runs", f"{overview['total_runs']:,}")
col2.metric("Total Wickets", f"{overview['total_wickets']:,}")
col3.metric("Sixes", f"{overview['total_sixes']:,}")
col4.metric("Fours", f"{overview['total_fours']:,}")

st.divider()

st.subheader("Season Archive")
st.caption("Every season, 2008-2026 — full match list and complete scorecards.")
seasons_sorted = sorted(matches["season_year"].unique(), reverse=True)
season_cols = st.columns(9)
for i, yr in enumerate(seasons_sorted):
    with season_cols[i % 9]:
        if st.button(str(yr), key=f"home_season_{yr}", width="stretch"):
            st.session_state["selected_season"] = yr
            st.switch_page("pages/9_Seasons.py")

st.divider()

st.subheader("Explore")
NAV_ITEMS = [
    ("#EC1C24", "Teams", "pages/7_Teams.py"),
    ("#004BA0", "IPL Overview", "pages/1_IPL_Overview.py"),
    ("#FDB913", "Player Analytics", "pages/2_Player_Analytics.py"),
    ("#3A225D", "Player Performance Predictor", "pages/6_Player_Performance.py"),
    ("#EA1A85", "Batter vs Bowler", "pages/3_Batter_vs_Bowler.py"),
    ("#17479E", "Venue Analytics", "pages/4_Venue_Analytics.py"),
    ("#FF822A", "Live Win Probability", "pages/5_Win_Probability.py"),
    ("#0D3692", "Season Archive", "pages/9_Seasons.py"),
    ("#B45309", "Records & Milestones", "pages/11_Records.py"),
    ("#0EA5E9", "Player Comparison", "pages/12_Player_Comparison.py"),
    ("#A72056", "Model Insights", "pages/13_Model_Insights.py"),
]
nav_cols = st.columns(3)
for i, (color, label, page) in enumerate(NAV_ITEMS):
    with nav_cols[i % 3]:
        with st.container(border=True):
            render_html(f'<div style="height:4px;background:{color};border-radius:2px;margin:-1px -1px 10px -1px;"></div>')
            st.page_link(page, label=label)

st.divider()

st.subheader("Top Run Scorers")
player_photos = load_player_photos()
top_batters = batting_stats.head(3)
cols = st.columns(3)
for col, (_, row) in zip(cols, top_batters.iterrows()):
    with col:
        color = team_color(row["current_team"]) if pd.notna(row.get("current_team")) else "#3B82F6"
        photo = avatar_html(row["player_name"], player_photos.get(row["player_id"]), size=80)
        render_html(
            f"""
            <div style="border-radius:14px;overflow:hidden;text-align:center;margin-bottom:8px;
                        background:linear-gradient(180deg,{color}55 0%,#131A3A 70%);
                        border:1px solid {color}88;padding:16px 8px 12px 8px;">
                <div style="display:flex;justify-content:center;">{photo}</div>
                <div style="color:white;font-weight:800;font-size:14px;font-family:sans-serif;margin-top:8px;">
                    {row['player_name']}
                </div>
                <div style="color:#B8C0E0;font-size:12px;font-family:sans-serif;">
                    {row['runs']:,} runs · SR {row['strike_rate']:.1f}
                </div>
            </div>
            """
        )

st.subheader("Top Wicket Takers")
top_bowlers = bowling_stats.head(3)
cols = st.columns(3)
for col, (_, row) in zip(cols, top_bowlers.iterrows()):
    with col:
        color = team_color(row["current_team"]) if pd.notna(row.get("current_team")) else "#3B82F6"
        photo = avatar_html(row["player_name"], player_photos.get(row["player_id"]), size=80)
        render_html(
            f"""
            <div style="border-radius:14px;overflow:hidden;text-align:center;margin-bottom:8px;
                        background:linear-gradient(180deg,{color}55 0%,#131A3A 70%);
                        border:1px solid {color}88;padding:16px 8px 12px 8px;">
                <div style="display:flex;justify-content:center;">{photo}</div>
                <div style="color:white;font-weight:800;font-size:14px;font-family:sans-serif;margin-top:8px;">
                    {row['player_name']}
                </div>
                <div style="color:#B8C0E0;font-size:12px;font-family:sans-serif;">
                    {int(row['wickets'])} wickets · Econ {row['economy']:.2f}
                </div>
            </div>
            """
        )

st.divider()
st.caption(
    f"Highest total: **{overview['highest_total']}**  |  "
    f"Lowest total: **{overview['lowest_total']}**  |  "
    "Data source: Cricsheet ball-by-ball records, 2008-2026."
)
