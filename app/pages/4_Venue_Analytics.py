import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import render_avatar
from app.data_loader import load_deliveries, load_venue_photos, load_venue_stats
from src.data.venue_normalization import canonical_venue_name

st.set_page_config(page_title="Venue Analytics | IPL Intelligence", page_icon="🏟️", layout="wide")
st.title("🏟️ Venue Analytics")

venue_stats = load_venue_stats()
deliveries = load_deliveries().copy()
deliveries["venue"] = deliveries["venue"].map(canonical_venue_name, na_action="ignore")
venue_photos = load_venue_photos()

venues = venue_stats.sort_values("matches_played", ascending=False)["venue"].tolist()
venue = st.selectbox("Select a venue", venues)

row = venue_stats[venue_stats["venue"] == venue].iloc[0]

photo_col, name_col = st.columns([1, 4])
with photo_col:
    render_avatar(venue, venue_photos.get(venue), size=100)
with name_col:
    st.subheader(venue)
    if pd.notna(row["city"]):
        st.caption(row["city"])

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
