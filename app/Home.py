import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from app.components import avatar_html, inject_theme_css
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

st.markdown(
    """
    <div style="border-radius:18px;overflow:hidden;margin-bottom:20px;padding:36px 32px;
                background:radial-gradient(circle at 10% 20%,#EC1C24 0%,#131A3A 45%,#0A0E27 100%);
                box-shadow:0 10px 28px rgba(0,0,0,0.4);">
        <div style="color:white;font-size:38px;font-weight:900;font-family:sans-serif;">🏏 IPL Intelligence</div>
        <div style="color:#DDE3FF;font-size:15px;font-family:sans-serif;margin-top:4px;">
            Cricket Analytics &amp; Win Prediction Platform — 19 seasons of IPL ball-by-ball data
        </div>
    </div>
    """,
    unsafe_allow_html=True,
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

st.subheader("Explore")
nav_col1, nav_col2, nav_col3 = st.columns(3)
with nav_col1:
    st.page_link("pages/8_Teams.py", label="🏆 Teams", icon="🏆")
    st.page_link("pages/1_IPL_Overview.py", label="📊 IPL Overview", icon="📊")
    st.page_link("pages/2_Player_Analytics.py", label="🧑 Player Analytics", icon="🧑")
with nav_col2:
    st.page_link("pages/7_Player_Performance.py", label="🔮 Player Performance Predictor", icon="🔮")
    st.page_link("pages/3_Batter_vs_Bowler.py", label="⚔️ Batter vs Bowler", icon="⚔️")
    st.page_link("pages/4_Venue_Analytics.py", label="🏟️ Venue Analytics", icon="🏟️")
with nav_col3:
    st.page_link("pages/5_Win_Probability.py", label="📈 Live Win Probability", icon="📈")
    st.page_link("pages/6_Model_Insights.py", label="🔬 Model Insights", icon="🔬")

st.divider()

st.subheader("Featured Players")
player_photos = load_player_photos()
top5 = batting_stats.head(5)
cols = st.columns(5)
for col, (_, row) in zip(cols, top5.iterrows()):
    with col:
        color = team_color(row["current_team"]) if pd.notna(row.get("current_team")) else "#3B82F6"
        photo = avatar_html(row["player_name"], player_photos.get(row["player_id"]), size=80)
        st.markdown(
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
            """,
            unsafe_allow_html=True,
        )

st.divider()
st.caption(
    "Top run scorer: **" + overview["top_run_scorer"] + "**  |  "
    "Leading wicket taker: **" + overview["leading_wicket_taker"] + "**  |  "
    f"Highest total: **{overview['highest_total']}**  |  "
    f"Lowest total: **{overview['lowest_total']}**"
)
