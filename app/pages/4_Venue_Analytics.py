import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import avatar_html, inject_theme_css
from app.data_loader import load_deliveries, load_venue_photos, load_venue_stats, team_color
from src.data.venue_normalization import canonical_venue_name

st.set_page_config(page_title="Venue Analytics | IPL Intelligence", page_icon="🏟️", layout="wide")
inject_theme_css()
st.title("🏟️ Venue Analytics")

venue_stats = load_venue_stats()
deliveries = load_deliveries().copy()
deliveries["venue"] = deliveries["venue"].map(canonical_venue_name, na_action="ignore")
venue_photos = load_venue_photos()

venues = venue_stats.sort_values("matches_played", ascending=False)["venue"].tolist()
venue = st.selectbox("Select a venue", venues)

row = venue_stats[venue_stats["venue"] == venue].iloc[0]

accent = team_color(row["most_successful_team"]) if pd.notna(row["most_successful_team"]) else "#3B82F6"
photo_html = avatar_html(venue, venue_photos.get(venue), size=90)
st.markdown(
    f"""
    <div style="border-radius:16px;overflow:hidden;margin-bottom:18px;display:flex;align-items:center;gap:18px;
                background:linear-gradient(90deg,{accent}44 0%,#131A3A 60%);border:1px solid {accent}66;
                padding:20px 24px;">
        {photo_html}
        <div style="color:white;font-family:sans-serif;">
            <div style="font-size:22px;font-weight:800;">{venue}</div>
            <div style="color:#B8C0E0;font-size:13px;">{row['city'] if pd.notna(row['city']) else ''}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()
cols = st.columns(6)
cols[0].metric("Matches", int(row["matches_played"]))
cols[1].metric("Avg 1st Innings Score", f"{row['avg_first_innings_score']:.0f}" if pd.notna(row["avg_first_innings_score"]) else "—")
cols[2].metric("Avg Powerplay Score", f"{row['avg_powerplay_score']:.0f}" if pd.notna(row["avg_powerplay_score"]) else "—")
cols[3].metric("Avg Death-Overs Score", f"{row['avg_death_overs_score']:.0f}" if pd.notna(row["avg_death_overs_score"]) else "—")
cols[4].metric("Chasing Win %", f"{row['chasing_win_pct']:.0f}%" if pd.notna(row["chasing_win_pct"]) else "—")
cols[5].metric("Most Successful Team", row["most_successful_team"] or "—")

st.divider()
st.subheader("Scoring by Over")
venue_deliveries = deliveries[(deliveries["venue"] == venue) & (~deliveries["is_super_over"])]
by_over = venue_deliveries.groupby("over")["runs_total"].mean().reset_index()
fig = px.bar(by_over, x="over", y="runs_total", labels={"over": "Over", "runs_total": "Average Runs"})
st.plotly_chart(fig, width="stretch")

st.divider()
st.subheader("All Venues")
st.dataframe(venue_stats, width="stretch", hide_index=True)
