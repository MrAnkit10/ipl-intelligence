import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from app.components import avatar_html, chart_card, inject_theme_css, render_html, render_page_title
from app.data_loader import load_matches, load_player_photos, load_season_awards, team_color
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

season_awards = load_season_awards()
award_row = season_awards[season_awards["season_year"] == season]
if not award_row.empty:
    award_row = award_row.iloc[0]
    player_photos = load_player_photos()

    st.divider()
    st.subheader("Season Awards")
    award_cols = st.columns(3)

    def _award_card(col, label: str, name, subtitle: str, player_id, accent: str) -> None:
        with col:
            with chart_card(label):
                if name is None or pd.isna(name):
                    st.caption("No result recorded.")
                    return
                photo = avatar_html(name, player_photos.get(player_id), size=64)
                render_html(
                    f"""
                    <div style="display:flex;align-items:center;gap:14px;">
                        {photo}
                        <div style="color:white;font-family:sans-serif;">
                            <div style="font-size:17px;font-weight:800;">{name}</div>
                            <div style="color:{accent};font-size:13px;font-weight:700;">{subtitle}</div>
                        </div>
                    </div>
                    """
                )

    _award_card(
        award_cols[0], "🟠 Orange Cap — Most Runs", award_row["orange_cap_name"],
        f"{int(award_row['orange_cap_runs'])} runs" if pd.notna(award_row["orange_cap_runs"]) else "",
        award_row["orange_cap_player_id"], "#FF822A",
    )
    _award_card(
        award_cols[1], "🟣 Purple Cap — Most Wickets", award_row["purple_cap_name"],
        f"{int(award_row['purple_cap_wickets'])} wickets" if pd.notna(award_row["purple_cap_wickets"]) else "",
        award_row["purple_cap_player_id"], "#A855F7",
    )
    _award_card(
        award_cols[2], "🏅 Player of the Final", award_row["final_potm_name"],
        "Player of the Match, final", award_row["final_potm_player_id"], "#3B82F6",
    )
    st.caption(
        "Cricsheet has no tournament-wide MVP/Player-of-the-Series field — only "
        "player_of_match per game, so that's the one award not shown here."
    )

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

display_cols = season_matches[
    ["date", "team1", "team2", "venue", "winner", "result_type", "win_by_runs", "win_by_wickets", "player_of_match"]
].copy()
display_cols["date"] = display_cols["date"].dt.strftime("%Y-%m-%d")
display_cols["margin"] = display_cols.apply(
    lambda r: f"{int(r['win_by_runs'])} runs" if pd.notna(r["win_by_runs"])
    else (f"{int(r['win_by_wickets'])} wkts" if pd.notna(r["win_by_wickets"]) else "—"),
    axis=1,
)
st.dataframe(
    display_cols[["date", "team1", "team2", "venue", "winner", "margin", "player_of_match"]].rename(
        columns={
            "team1": "Team 1", "team2": "Team 2", "venue": "Venue", "winner": "Winner",
            "margin": "Margin", "date": "Date", "player_of_match": "Player of the Match",
        }
    ),
    width="stretch", hide_index=True, height=480,
)
