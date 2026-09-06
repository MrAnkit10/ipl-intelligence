import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import render_avatar
from app.data_loader import (
    load_batting_stats,
    load_bowling_stats,
    load_deliveries,
    load_dismissal_breakdown,
    load_player_photos,
)

st.set_page_config(page_title="Player Analytics | IPL Intelligence", page_icon="🧑", layout="wide")
st.title("🧑 Player Analytics")

batting_stats = load_batting_stats()
bowling_stats = load_bowling_stats()
deliveries = load_deliveries()
player_photos = load_player_photos()
dismissal_breakdown = load_dismissal_breakdown()

all_players = sorted(set(batting_stats["player_name"]) | set(bowling_stats["player_name"]))
player_name = st.selectbox("Select a player", all_players, index=all_players.index("V Kohli") if "V Kohli" in all_players else 0)

bat_row = batting_stats[batting_stats["player_name"] == player_name]
bowl_row = bowling_stats[bowling_stats["player_name"] == player_name]
player_id = (bat_row["player_id"].iloc[0] if not bat_row.empty else bowl_row["player_id"].iloc[0])
current_team = (
    bat_row["current_team"].iloc[0] if not bat_row.empty and pd.notna(bat_row["current_team"].iloc[0])
    else (bowl_row["current_team"].iloc[0] if not bowl_row.empty else None)
)

photo_col, name_col = st.columns([1, 4])
with photo_col:
    render_avatar(player_name, player_photos.get(player_id))
with name_col:
    st.subheader(player_name)
    if current_team:
        st.caption(current_team)

st.divider()

if not bat_row.empty:
    row = bat_row.iloc[0]
    st.subheader("Batting")
    cols = st.columns(6)
    cols[0].metric("Innings", int(row["innings"]))
    cols[1].metric("Runs", int(row["runs"]))
    cols[2].metric("Average", f"{row['batting_average']:.1f}" if pd.notna(row["batting_average"]) else "—")
    cols[3].metric("Strike Rate", f"{row['strike_rate']:.1f}")
    cols[4].metric("50s", int(row["fifties"]))
    cols[5].metric("100s", int(row["hundreds"]))

    comp_col, dismiss_col = st.columns(2)
    with comp_col:
        st.markdown("**Run Composition**")
        stroke_counts = {
            "1s": row["ones"], "2s": row["twos"], "3s": row["threes"],
            "4s": row["fours"], "5s": row["fives"], "6s": row["sixes"],
        }
        stroke_runs = {
            "1s": row["ones"] * 1, "2s": row["twos"] * 2, "3s": row["threes"] * 3,
            "4s": row["fours"] * 4, "5s": row["fives"] * 5, "6s": row["sixes"] * 6,
        }
        comp_df = pd.DataFrame(
            {
                "stroke": list(stroke_counts.keys()),
                "count": list(stroke_counts.values()),
                "runs_contributed": list(stroke_runs.values()),
            }
        )
        comp_df = comp_df[comp_df["count"] > 0]
        fig_comp = px.bar(
            comp_df, x="stroke", y="runs_contributed", text="count",
            labels={"runs_contributed": "Runs contributed", "stroke": ""},
            hover_data={"count": True},
        )
        fig_comp.update_traces(texttemplate="%{text} times", textposition="outside")
        st.plotly_chart(fig_comp, width="stretch")
        st.caption(
            f"{row['runs']} runs = {int(row['ones'])} singles + {int(row['twos'])} twos + "
            f"{int(row['threes'])} threes + {int(row['fours'])} fours + {int(row['fives'])} fives + "
            f"{int(row['sixes'])} sixes. {row['runs_from_boundaries_pct']:.0f}% of runs came from boundaries."
        )

    with dismiss_col:
        st.markdown("**How They Get Out**")
        player_dismissals = dismissal_breakdown[dismissal_breakdown["player_id"] == player_id]
        if not player_dismissals.empty:
            fig_dismiss = px.pie(player_dismissals, names="dismissal_kind", values="count", hole=0.4)
            st.plotly_chart(fig_dismiss, width="stretch")
        else:
            st.caption("Never dismissed in this dataset.")

    phase_cols = [c for c in ["strike_rate_powerplay", "strike_rate_middle", "strike_rate_death"] if c in row.index]
    phase_df = pd.DataFrame(
        {
            "phase": [c.replace("strike_rate_", "").title() for c in phase_cols],
            "strike_rate": [row[c] for c in phase_cols],
        }
    ).dropna()
    if not phase_df.empty:
        fig = px.bar(phase_df, x="phase", y="strike_rate", title="Strike Rate by Phase", text="strike_rate")
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        st.plotly_chart(fig, width="stretch")

    player_deliveries = deliveries[
        (deliveries["batter"] == player_name) & (~deliveries["is_super_over"]) & (deliveries["extra_wides"] == 0)
    ]
    innings_runs = (
        player_deliveries.groupby(["match_id", "date"])["runs_batter"].sum().reset_index().sort_values("date")
    )
    if len(innings_runs) > 0:
        recent = innings_runs.tail(15)
        fig_form = px.bar(recent, x="date", y="runs_batter", title="Recent Form (last 15 innings)")
        st.plotly_chart(fig_form, width="stretch")

if not bowl_row.empty:
    row = bowl_row.iloc[0]
    st.subheader("Bowling")
    cols = st.columns(6)
    cols[0].metric("Overs", f"{row['overs']:.1f}")
    cols[1].metric("Wickets", int(row["wickets"]))
    cols[2].metric("Economy", f"{row['economy']:.2f}")
    cols[3].metric(
        "Bowling Average", f"{row['bowling_average']:.1f}" if pd.notna(row["bowling_average"]) else "—"
    )
    cols[4].metric("Dot Ball %", f"{row['dot_ball_pct']:.1f}%")
    cols[5].metric("Boundary Conceded %", f"{row['boundary_conceded_pct']:.1f}%")

    phase_cols = [c for c in ["economy_powerplay", "economy_middle", "economy_death"] if c in row.index]
    phase_df = pd.DataFrame(
        {
            "phase": [c.replace("economy_", "").title() for c in phase_cols],
            "economy": [row[c] for c in phase_cols],
        }
    ).dropna()
    if not phase_df.empty:
        fig = px.bar(phase_df, x="phase", y="economy", title="Economy by Phase", text="economy")
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        st.plotly_chart(fig, width="stretch")

if bat_row.empty and bowl_row.empty:
    st.info("No stats available for this player.")
