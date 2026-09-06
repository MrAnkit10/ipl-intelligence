import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from app.components import inject_theme_css
from app.data_loader import load_team_stats, team_color
from src.data.team_normalization import team_code

st.set_page_config(page_title="Teams | IPL Intelligence", page_icon="🏆", layout="wide")
inject_theme_css()
st.title("🏆 Teams")
st.caption(
    "Team badges are colored code chips, not official crests — those are trademarked and "
    "not safe to hotlink on a public deployment. Click through to Team Analytics for the "
    "full head-to-head and toss/venue breakdowns."
)

team_stats = load_team_stats().sort_values("win_pct", ascending=False).reset_index(drop=True)


def render_team_card(team: str, matches: int, wins: int, losses: int, win_pct: float) -> None:
    color = team_color(team)
    code = team_code(team)
    st.markdown(
        f"""
        <div style="border-radius:16px;overflow:hidden;margin-bottom:18px;
                    box-shadow:0 8px 20px rgba(0,0,0,0.35);">
            <div style="background:radial-gradient(circle at 30% 20%,{color}FF 0%,{color}99 55%,#0A0E2733 100%);
                        height:120px;display:flex;align-items:center;justify-content:center;">
                <div style="font-size:44px;font-weight:900;color:white;font-family:sans-serif;
                            text-shadow:0 2px 8px rgba(0,0,0,0.4);letter-spacing:1px;">
                    {code}
                </div>
            </div>
            <div style="background:{color};padding:12px 16px;">
                <div style="color:white;font-weight:800;font-size:16px;font-family:sans-serif;">{team}</div>
            </div>
            <div style="background:#131A3A;padding:10px 16px;display:flex;justify-content:space-between;
                        color:#B8C0E0;font-family:sans-serif;font-size:13px;">
                <span>{matches} played</span>
                <span>{wins}W - {losses}L</span>
                <span style="color:white;font-weight:700;">{win_pct:.0f}%</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


cols_per_row = 3
rows = [team_stats.iloc[i : i + cols_per_row] for i in range(0, len(team_stats), cols_per_row)]
for row_df in rows:
    cols = st.columns(cols_per_row)
    for col, (_, team_row) in zip(cols, row_df.iterrows()):
        with col:
            render_team_card(
                team_row["team"],
                int(team_row["matches_played"]),
                int(team_row["wins"]),
                int(team_row["losses"]),
                team_row["win_pct"] if pd.notna(team_row["win_pct"]) else 0.0,
            )
