import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import avatar_html, chart_card, inject_theme_css, render_html, render_page_title
from app.data_loader import load_batting_percentiles, load_batting_stats, load_player_photos, team_color
from src.analytics.batting import PERCENTILE_METRICS

st.set_page_config(page_title="Player Comparison | IPL Intelligence", page_icon="🆚", layout="wide")
inject_theme_css()
render_page_title(
    "Player Comparison",
    "Two players, side by side — career numbers and a percentile radar overlay (15+ innings pool).",
    "#0EA5E9",
)

batting_stats = load_batting_stats()
percentiles = load_batting_percentiles()
player_photos = load_player_photos()

eligible = batting_stats[batting_stats["innings"] >= 5].sort_values("runs", ascending=False)
players = eligible["player_name"].tolist()

col1, col2 = st.columns(2)
p1_name = col1.selectbox("Player 1", players, index=players.index("V Kohli") if "V Kohli" in players else 0)
default_p2 = "RG Sharma" if "RG Sharma" in players else players[1]
p2_name = col2.selectbox("Player 2", players, index=players.index(default_p2) if default_p2 in players else 1)

P1_COLOR, P2_COLOR = "#EC1C24", "#3B82F6"


def _row(name: str) -> pd.Series:
    return batting_stats[batting_stats["player_name"] == name].iloc[0]


def _identity_card(row: pd.Series, color: str) -> None:
    photo = avatar_html(row["player_name"], player_photos.get(row["player_id"]), size=76)
    render_html(
        f"""
        <div style="border-radius:14px;overflow:hidden;display:flex;align-items:center;gap:16px;
                    background:linear-gradient(90deg,{color}55 0%,#131A3A 70%);border:1px solid {color}88;
                    padding:18px 22px;">
            {photo}
            <div style="color:white;font-family:sans-serif;">
                <div style="font-size:20px;font-weight:900;">{row['player_name']}</div>
                <div style="color:#B8C0E0;font-size:13px;">{row.get('current_team') or ''}</div>
            </div>
        </div>
        """
    )


row1, row2 = _row(p1_name), _row(p2_name)
id_col1, id_col2 = st.columns(2)
with id_col1:
    _identity_card(row1, P1_COLOR)
with id_col2:
    _identity_card(row2, P2_COLOR)

st.divider()

with chart_card("Career Comparison"):
    compare_fields = [
        ("Matches", "matches_played", "{:.0f}"),
        ("Runs", "runs", "{:,.0f}"),
        ("Highest Score", "highest_score", "{:.0f}"),
        ("Average", "batting_average", "{:.1f}"),
        ("Strike Rate", "strike_rate", "{:.1f}"),
        ("100s / 50s", None, None),
        ("4s / 6s", None, None),
        ("Catches", "catches", "{:.0f}"),
    ]
    table_rows = []
    for label, field, fmt in compare_fields:
        if field is None and label == "100s / 50s":
            v1 = f"{int(row1['hundreds'])} / {int(row1['fifties'])}"
            v2 = f"{int(row2['hundreds'])} / {int(row2['fifties'])}"
        elif field is None and label == "4s / 6s":
            v1 = f"{int(row1['fours'])} / {int(row1['sixes'])}"
            v2 = f"{int(row2['fours'])} / {int(row2['sixes'])}"
        else:
            v1 = fmt.format(row1[field]) if pd.notna(row1.get(field)) else "—"
            v2 = fmt.format(row2[field]) if pd.notna(row2.get(field)) else "—"
        table_rows.append({p1_name: v1, "Stat": label, p2_name: v2})
    compare_df = pd.DataFrame(table_rows)[[p1_name, "Stat", p2_name]]
    st.dataframe(compare_df, width="stretch", hide_index=True)

p1_pct = percentiles[percentiles["player_id"] == row1["player_id"]]
p2_pct = percentiles[percentiles["player_id"] == row2["player_id"]]

if not p1_pct.empty and not p2_pct.empty and row1["innings"] >= 5 and row2["innings"] >= 5:
    p1_pct, p2_pct = p1_pct.iloc[0], p2_pct.iloc[0]
    labels = [PERCENTILE_METRICS[m][0] for m in PERCENTILE_METRICS]

    with chart_card(
        "Percentile Radar Overlay",
        "Each axis is a percentile (0-100) against players with 15+ career innings — how these two rank against the league.",
    ):
        fig = go.Figure()
        for row, pct_row, name, color in [(row1, p1_pct, p1_name, P1_COLOR), (row2, p2_pct, p2_name, P2_COLOR)]:
            values = [pct_row[m] if pd.notna(pct_row[m]) else 0 for m in PERCENTILE_METRICS]
            fig.add_trace(
                go.Scatterpolar(
                    r=values + [values[0]], theta=labels + [labels[0]],
                    name=name, line=dict(color=color, width=2), fill="toself", fillcolor=f"{color}22",
                )
            )
        fig.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(range=[0, 100], showticklabels=False, gridcolor="#232B55", linecolor="#232B55"),
                angularaxis=dict(gridcolor="#232B55", linecolor="#232B55", color="#B8C0E0", tickfont=dict(size=11)),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=-0.12, font=dict(color="#B8C0E0")),
            margin=dict(l=40, r=40, t=20, b=10),
            height=480,
        )
        st.plotly_chart(fig, width="stretch")
else:
    st.caption("One or both players need at least 5 career innings for a percentile radar comparison.")
