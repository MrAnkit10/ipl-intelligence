import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from app.components import inject_theme_css, render_page_title
from app.data_loader import load_matches, team_color
from src.data.team_normalization import canonical_team_name

st.set_page_config(page_title="Seasons | IPL Intelligence", page_icon="🏏", layout="wide")
inject_theme_css()
render_page_title("Seasons Archive", "Browse every season from 2008 to 2026 — click any match for its full scorecard")

matches = load_matches().copy()
for col in ["team1", "team2", "toss_winner", "winner"]:
    matches[col] = matches[col].map(canonical_team_name, na_action="ignore")

seasons = sorted(matches["season_year"].unique(), reverse=True)
default_season = st.session_state.get("selected_season", seasons[0])
if default_season not in seasons:
    default_season = seasons[0]

season = st.selectbox("Season", seasons, index=seasons.index(default_season))
st.session_state["selected_season"] = season

season_matches = matches[matches["season_year"] == season].sort_values("date").reset_index(drop=True)

# The final is the last match of the season by date; its winner is the champion.
final_match = season_matches.iloc[-1]
champion = final_match["winner"] if final_match["outcome_type"] == "win" else None

col1, col2, col3 = st.columns(3)
col1.metric("Matches", len(season_matches))
col2.metric("Champion", champion or "—")
col3.metric("Season Label", season_matches["season"].iloc[0])

st.divider()
st.subheader(f"All Matches — {season}")

season_matches["label"] = (
    season_matches["date"].dt.strftime("%d %b")
    + " | "
    + season_matches["team1"]
    + " vs "
    + season_matches["team2"]
    + " | "
    + season_matches["venue"]
)

picked_label = st.selectbox("Pick a match for its full scorecard", season_matches["label"].tolist())
picked_match_id = int(season_matches.loc[season_matches["label"] == picked_label, "match_id"].iloc[0])
if st.button("Open Scorecard →"):
    st.session_state["selected_match_id"] = picked_match_id
    st.switch_page("pages/10_Match_Detail.py")

display_cols = season_matches[["date", "team1", "team2", "venue", "winner", "result_type", "win_by_runs", "win_by_wickets"]].copy()
display_cols["date"] = display_cols["date"].dt.strftime("%Y-%m-%d")
display_cols["margin"] = display_cols.apply(
    lambda r: f"{int(r['win_by_runs'])} runs" if pd.notna(r["win_by_runs"])
    else (f"{int(r['win_by_wickets'])} wkts" if pd.notna(r["win_by_wickets"]) else "—"),
    axis=1,
)
st.dataframe(
    display_cols[["date", "team1", "team2", "venue", "winner", "margin"]].rename(
        columns={"team1": "Team 1", "team2": "Team 2", "venue": "Venue", "winner": "Winner", "margin": "Margin", "date": "Date"}
    ),
    width="stretch", hide_index=True, height=480,
)
