import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components import avatar_html, chart_card, inject_theme_css, render_html, render_page_title
from app.data_loader import (
    load_batting_percentiles,
    load_batting_stats,
    load_bowling_stats,
    load_deliveries,
    load_dismissal_breakdown,
    load_player_photos,
    team_color,
)
from src.analytics.batting import GROUP_COLORS, PERCENTILE_METRICS

TRANSPARENT_LAYOUT = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
PHASE_COLORS = ["#3B82F6", "#EAB308", "#EF4444"]

st.set_page_config(page_title="Player Analytics | IPL Intelligence", page_icon="🧑", layout="wide")
inject_theme_css()
render_page_title("Player Analytics", "Career batting and bowling records, form, and phase splits", "#FDB913")

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

color = team_color(current_team) if current_team else "#3B82F6"
photo = avatar_html(player_name, player_photos.get(player_id), size=88)
render_html(
    f"""
    <div style="border-radius:16px;overflow:hidden;margin-bottom:18px;display:flex;align-items:center;gap:18px;
                background:linear-gradient(90deg,{color}55 0%,#131A3A 60%);border:1px solid {color}88;
                padding:20px 24px;">
        {photo}
        <div style="color:white;font-family:sans-serif;">
            <div style="font-size:24px;font-weight:800;">{player_name}</div>
            <div style="color:#B8C0E0;font-size:13px;">{current_team or ''}</div>
        </div>
    </div>
    """
)

# Role and career span are computed from every appearance (batting or
# bowling) so they show correctly for bowlers too, not just batters —
# batting_stats' debut/highest-score columns only cover batting innings.
# Bowling type (pace/spin, left/right-arm) isn't derivable from Cricsheet
# ball-by-ball data or the player register, so it's never guessed at here.
has_bat = not bat_row.empty
has_bowl = not bowl_row.empty
bat_wickets_ok = has_bowl and bowl_row.iloc[0]["wickets"] >= 20
bat_innings_ok = has_bat and bat_row.iloc[0]["innings"] >= 20
if bat_innings_ok and bat_wickets_ok:
    role = "All-rounder"
elif has_bat:
    role = "Batter"
elif has_bowl:
    role = "Bowler"
else:
    role = "Player"

player_apps = deliveries[
    ((deliveries["batter_id"] == player_id) | (deliveries["bowler_id"] == player_id)) & (~deliveries["is_super_over"])
]
debut = player_apps["date"].min() if not player_apps.empty else None
last_played = player_apps["date"].max() if not player_apps.empty else None
matches_played = int(player_apps["match_id"].nunique()) if not player_apps.empty else 0
seasons_span = f"{debut.year}–{last_played.year}" if debut is not None and last_played is not None else "—"

render_html(
    f"""
    <div style="display:flex;gap:18px;align-items:center;margin:-6px 0 14px 0;flex-wrap:wrap;">
        <span style="color:white;background:{color};padding:3px 12px;border-radius:20px;
                    font-size:12px;font-weight:800;font-family:sans-serif;letter-spacing:0.02em;">{role.upper()}</span>
        <span style="color:#8892C0;font-size:12px;font-family:sans-serif;">{seasons_span} · {matches_played} matches</span>
        <span style="color:#8892C0;font-size:12px;font-family:sans-serif;">
            Debut {debut.strftime('%b %d, %Y') if debut is not None else '—'}
            &nbsp;·&nbsp; Last played {last_played.strftime('%b %d, %Y') if last_played is not None else '—'}
        </span>
    </div>
    """
)

if not bat_row.empty:
    row = bat_row.iloc[0]

    st.subheader("Batting")
    cols = st.columns(8)
    cols[0].metric("Matches", matches_played)
    cols[1].metric("Runs", int(row["runs"]))
    cols[2].metric("Average", f"{row['batting_average']:.1f}" if pd.notna(row["batting_average"]) else "—")
    cols[3].metric("Strike Rate", f"{row['strike_rate']:.1f}")
    cols[4].metric("Highest", int(row["highest_score"]) if pd.notna(row.get("highest_score")) else "—")
    cols[5].metric("100s / 50s", f"{int(row['hundreds'])} / {int(row['fifties'])}")
    cols[6].metric("4s / 6s", f"{int(row['fours'])} / {int(row['sixes'])}")
    cols[7].metric("Catches", int(row["catches"]) if pd.notna(row.get("catches")) else "—")

    percentiles = load_batting_percentiles()
    prow = percentiles[percentiles["player_id"] == player_id]
    if not prow.empty and row["innings"] >= 5:
        prow = prow.iloc[0]
        with chart_card(
            "Career Dossier",
            "Every spoke is a percentile (0-100) against players with 15+ career innings — "
            "how this player's rate stats rank against the league, not raw counting stats.",
        ):
            labels = [PERCENTILE_METRICS[m][0] for m in PERCENTILE_METRICS]
            groups = [PERCENTILE_METRICS[m][1] for m in PERCENTILE_METRICS]
            values = [prow[m] for m in PERCENTILE_METRICS]
            raw_fmt = {
                "boundary_pct": "{:.1f}%", "six_rate": "{:.1f}", "strike_rate_death": "{:.1f}",
                "chase_strike_rate": "{:.1f}", "batting_average": "{:.1f}", "big_score_pct": "{:.0f}%",
                "conversion_pct": "{:.0f}%", "balls_per_boundary": "{:.1f}", "dot_ball_pct": "{:.0f}%",
                "fifty_rate": "{:.0f}%", "strike_rate_middle": "{:.1f}", "acceleration": "{:.2f}x",
            }
            raw_values = [
                raw_fmt[m].format(row[m]) if pd.notna(row.get(m)) else "—" for m in PERCENTILE_METRICS
            ]

            fig = go.Figure()
            for group_key in ["power", "consistency", "tempo"]:
                idx = [i for i, g in enumerate(groups) if g == group_key]
                fig.add_trace(
                    go.Barpolar(
                        r=[values[i] if pd.notna(values[i]) else 0 for i in idx],
                        theta=[labels[i] for i in idx],
                        name=group_key.capitalize(),
                        marker_color=GROUP_COLORS[group_key],
                        marker_line_color="#0A0E27",
                        marker_line_width=1,
                        opacity=0.85,
                        hovertext=[f"{labels[i]}: {raw_values[i]} (percentile {values[i]:.0f})" for i in idx],
                        hoverinfo="text",
                    )
                )
            fig.add_trace(
                go.Scatterpolar(
                    r=[min(v, 96) + 4 if pd.notna(v) else 4 for v in values],
                    theta=labels,
                    mode="text",
                    text=raw_values,
                    textfont=dict(color="white", size=11),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            fig.update_layout(
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(range=[0, 100], showticklabels=False, gridcolor="#232B55", linecolor="#232B55"),
                    angularaxis=dict(
                        categoryarray=labels, direction="clockwise", rotation=90,
                        gridcolor="#232B55", linecolor="#232B55", color="#B8C0E0", tickfont=dict(size=11),
                    ),
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=-0.12, font=dict(color="#B8C0E0")),
                margin=dict(l=30, r=30, t=10, b=10),
                height=460,
            )
            st.plotly_chart(fig, width="stretch")
    elif row["innings"] < 5:
        st.caption("Career Dossier needs at least 5 career innings to produce a meaningful percentile ranking.")

    comp_col, dismiss_col = st.columns(2)
    with comp_col:
        with chart_card(
            "Scoring Wheel",
            "Career runs by shot value — wedge size is runs contributed by that stroke. "
            "This is a run-value breakdown, not a shot-direction wagon wheel: Cricsheet has no "
            "field-placement data, so this project never guesses at one.",
        ):
            strokes = ["1s", "2s", "3s", "4s", "5s", "6s"]
            counts = [row["ones"], row["twos"], row["threes"], row["fours"], row["fives"], row["sixes"]]
            run_values = [1, 2, 3, 4, 5, 6]
            runs_contributed = [c * v for c, v in zip(counts, run_values)]
            wheel_colors = ["#3B82F6", "#22C55E", "#EAB308", "#F97316", "#A855F7", "#EF4444"]

            fig_wheel = go.Figure()
            fig_wheel.add_trace(
                go.Barpolar(
                    r=runs_contributed,
                    theta=[i * 60 for i in range(6)],
                    width=[58] * 6,
                    marker_color=wheel_colors,
                    marker_line_color="#0A0E27",
                    marker_line_width=2,
                    opacity=0.9,
                    hovertext=[
                        f"{s}: {int(c)} times · {rc} runs contributed" for s, c, rc in zip(strokes, counts, runs_contributed)
                    ],
                    hoverinfo="text",
                )
            )
            fig_wheel.add_trace(
                go.Scatterpolar(
                    r=[max(rc, 1) * 1.18 for rc in runs_contributed],
                    theta=[i * 60 for i in range(6)],
                    mode="text",
                    text=[f"{s}<br>{int(c)}×" for s, c in zip(strokes, counts)],
                    textfont=dict(color="white", size=12),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            fig_wheel.update_layout(
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(showticklabels=False, gridcolor="#232B55", linecolor="#232B55"),
                    angularaxis=dict(showticklabels=False, gridcolor="#232B55", linecolor="#232B55"),
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                margin=dict(l=30, r=30, t=30, b=10),
                height=380,
            )
            st.plotly_chart(fig_wheel, width="stretch")
            st.caption(
                f"{row['runs']} runs = {int(row['ones'])} singles + {int(row['twos'])} twos + "
                f"{int(row['threes'])} threes + {int(row['fours'])} fours + {int(row['fives'])} fives + "
                f"{int(row['sixes'])} sixes. {row['runs_from_boundaries_pct']:.0f}% of runs came from boundaries."
            )

    with dismiss_col:
        with chart_card("How They Get Out", "Dismissal types across their whole career"):
            player_dismissals = dismissal_breakdown[dismissal_breakdown["player_id"] == player_id]
            if not player_dismissals.empty:
                fig_dismiss = px.pie(
                    player_dismissals, names="dismissal_kind", values="count", hole=0.5,
                    color_discrete_sequence=px.colors.sequential.Blues_r,
                )
                fig_dismiss.update_layout(**TRANSPARENT_LAYOUT, legend=dict(font=dict(color="#B8C0E0")))
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
        with chart_card("Strike Rate by Phase", "Powerplay / Middle / Death"):
            fig = go.Figure(
                go.Bar(
                    x=phase_df["strike_rate"], y=phase_df["phase"], orientation="h",
                    marker_color=PHASE_COLORS[: len(phase_df)],
                    text=[f"{v:.1f}" for v in phase_df["strike_rate"]], textposition="outside",
                )
            )
            fig.update_layout(**TRANSPARENT_LAYOUT, height=190, margin=dict(l=10, r=30, t=10, b=10), font=dict(color="#B8C0E0"), xaxis_title="", yaxis_title="")
            st.plotly_chart(fig, width="stretch")

    player_deliveries = deliveries[
        (deliveries["batter"] == player_name) & (~deliveries["is_super_over"]) & (deliveries["extra_wides"] == 0)
    ]
    innings_runs = (
        player_deliveries.groupby(["match_id", "date"])["runs_batter"].sum().reset_index().sort_values("date")
    )
    if len(innings_runs) > 0:
        with chart_card("Recent Form", "Runs in the last 15 innings"):
            recent = innings_runs.tail(15)
            fig_form = go.Figure(
                go.Scatter(
                    x=recent["date"], y=recent["runs_batter"], mode="lines+markers",
                    line=dict(color=color, width=2.5, shape="spline"),
                    marker=dict(size=7, color=color, line=dict(color="#0A0E27", width=1)),
                    fill="tozeroy", fillcolor=f"{color}22",
                )
            )
            avg_line = recent["runs_batter"].mean()
            fig_form.add_hline(y=avg_line, line_dash="dot", line_color="#8892C0", annotation_text="avg", annotation_font_color="#8892C0")
            fig_form.update_layout(
                **TRANSPARENT_LAYOUT, height=240, margin=dict(l=10, r=10, t=10, b=10),
                font=dict(color="#B8C0E0"), xaxis_title="", yaxis_title="Runs",
            )
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
        with chart_card("Economy by Phase", "Powerplay / Middle / Death"):
            fig = go.Figure(
                go.Bar(
                    x=phase_df["economy"], y=phase_df["phase"], orientation="h",
                    marker_color=PHASE_COLORS[: len(phase_df)],
                    text=[f"{v:.2f}" for v in phase_df["economy"]], textposition="outside",
                )
            )
            fig.update_layout(**TRANSPARENT_LAYOUT, height=190, margin=dict(l=10, r=30, t=10, b=10), font=dict(color="#B8C0E0"), xaxis_title="", yaxis_title="")
            st.plotly_chart(fig, width="stretch")

if bat_row.empty and bowl_row.empty:
    st.info("No stats available for this player.")
