import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from app.components import chart_card, inject_theme_css, render_match_banner, render_page_title
from app.data_loader import load_deliveries, load_matches, team_color
from src.analytics.scorecard import compute_match_scorecard
from src.data.team_normalization import canonical_team_name

st.set_page_config(page_title="Match Scorecard | IPL Intelligence", page_icon="🏏", layout="wide")
inject_theme_css()

matches = load_matches().copy()
for col in ["team1", "team2", "toss_winner", "winner"]:
    matches[col] = matches[col].map(canonical_team_name, na_action="ignore")
deliveries = load_deliveries()

match_ids = matches.sort_values("date", ascending=False)
default_match_id = st.session_state.get("selected_match_id", match_ids["match_id"].iloc[0])
if default_match_id not in match_ids["match_id"].values:
    default_match_id = match_ids["match_id"].iloc[0]

match_ids["label"] = (
    match_ids["date"].dt.strftime("%Y-%m-%d") + " | " + match_ids["team1"] + " vs " + match_ids["team2"]
)
default_label = match_ids.loc[match_ids["match_id"] == default_match_id, "label"].iloc[0]
picked_label = st.selectbox("Match", match_ids["label"].tolist(), index=match_ids["label"].tolist().index(default_label))
match_id = int(match_ids.loc[match_ids["label"] == picked_label, "match_id"].iloc[0])
st.session_state["selected_match_id"] = match_id

match_row = matches[matches["match_id"] == match_id].iloc[0]
innings = compute_match_scorecard(match_id, deliveries)

render_page_title("Match Scorecard")

if len(innings) >= 2:
    result_text = (
        f"{match_row['winner'] or 'No result'} "
        + (f"won by {int(match_row['win_by_runs'])} runs" if pd.notna(match_row["win_by_runs"]) else "")
        + (f"won by {int(match_row['win_by_wickets'])} wickets" if pd.notna(match_row["win_by_wickets"]) else "")
    )
    potm = f" · Player of the Match: {match_row['player_of_match']}" if pd.notna(match_row.get("player_of_match")) else ""
    subtitle = f"{result_text} · {match_row['venue']} · {match_row['date'].strftime('%d %b %Y')}{potm}"
    render_match_banner(
        innings[0]["batting_team"], team_color(innings[0]["batting_team"]),
        f"{innings[0]['total_runs']}/{innings[0]['total_wickets']} ({innings[0]['overs']})",
        innings[1]["batting_team"], team_color(innings[1]["batting_team"]),
        f"{innings[1]['total_runs']}/{innings[1]['total_wickets']} ({innings[1]['overs']})",
        subtitle,
    )
else:
    st.info(f"{match_row['venue']} · {match_row['date'].strftime('%d %b %Y')} — no result (abandoned)")

for inn in innings:
    st.divider()
    color = team_color(inn["batting_team"])
    with chart_card(
        f"{inn['batting_team']}: {inn['total_runs']}/{inn['total_wickets']} ({inn['overs']} overs)"
    ):
        bat_col, bowl_col = st.columns([3, 2])
        with bat_col:
            st.markdown("**Batting**")
            bat_df = pd.DataFrame(inn["batting"])
            if not bat_df.empty:
                bat_df = bat_df.rename(
                    columns={
                        "batter": "Batter", "how_out": "Dismissal", "runs": "R", "balls": "B",
                        "fours": "4s", "sixes": "6s", "strike_rate": "SR",
                    }
                )
                st.dataframe(bat_df, width="stretch", hide_index=True)
            extras = inn["extras"]
            total_extras = sum(extras.values())
            st.caption(
                f"Extras: {total_extras} (wd {extras['wides']}, nb {extras['no_balls']}, "
                f"b {extras['byes']}, lb {extras['leg_byes']}, pen {extras['penalty']})"
            )
        with bowl_col:
            st.markdown("**Bowling**")
            bowl_df = pd.DataFrame(inn["bowling"])
            if not bowl_df.empty:
                bowl_df = bowl_df.rename(
                    columns={"bowler": "Bowler", "overs": "O", "maidens": "M", "runs": "R", "wickets": "W", "economy": "Econ"}
                )
                st.dataframe(bowl_df, width="stretch", hide_index=True)

        if inn["fall_of_wickets"]:
            fow_text = " · ".join(
                f"{w['wicket_number']}-{w['score']} ({w['player']}, {w['over']} ov)" for w in inn["fall_of_wickets"]
            )
            st.caption(f"Fall of wickets: {fow_text}")
