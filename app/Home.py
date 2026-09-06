import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

from app.components import render_avatar
from app.data_loader import load_batting_stats, load_bowling_stats, load_deliveries, load_matches, load_player_photos
from src.analytics.overview import compute_overview

st.set_page_config(page_title="IPL Intelligence", page_icon="🏏", layout="wide")

matches = load_matches()
deliveries = load_deliveries()
batting_stats = load_batting_stats()
bowling_stats = load_bowling_stats()
overview = compute_overview(matches, deliveries, batting_stats, bowling_stats)

st.title("🏏 IPL Intelligence")
st.caption("Cricket Analytics & Win Prediction Platform — 19 seasons of IPL ball-by-ball data")

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
    st.page_link("pages/1_IPL_Overview.py", label="📊 IPL Overview", icon="📊")
    st.page_link("pages/2_Player_Analytics.py", label="🧑 Player Analytics", icon="🧑")
    st.page_link("pages/7_Player_Performance.py", label="🔮 Player Performance Predictor", icon="🔮")
with nav_col2:
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
        render_avatar(row["player_name"], player_photos.get(row["player_id"]), size=90)
        st.markdown(f"**{row['player_name']}**")
        st.caption(f"{row['runs']:,} runs · SR {row['strike_rate']:.1f}")

st.divider()
st.caption(
    "Top run scorer: **" + overview["top_run_scorer"] + "**  |  "
    "Leading wicket taker: **" + overview["leading_wicket_taker"] + "**  |  "
    f"Highest total: **{overview['highest_total']}**  |  "
    f"Lowest total: **{overview['lowest_total']}**"
)
