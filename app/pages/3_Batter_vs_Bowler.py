import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import chart_card, inject_theme_css, render_matchup_banner, render_page_title
from app.data_loader import load_deliveries, load_player_photos, team_color
from src.data.team_normalization import canonical_team_name

st.set_page_config(page_title="Batter vs Bowler | IPL Intelligence", page_icon="⚔️", layout="wide")
inject_theme_css()
render_page_title(
    "Batter vs Bowler Matchup",
    "Historical head-to-head from ball-by-ball data. A model-based next-ball outcome "
    "distribution (blueprint Module 5) is a planned extension, not yet built.",
    "#EA1A85",
)

deliveries = load_deliveries()
main = deliveries[~deliveries["is_super_over"]]
player_photos = load_player_photos()

batter_name_to_id = dict(zip(main["batter"], main["batter_id"]))
bowler_name_to_id = dict(zip(main["bowler"], main["bowler_id"]))

batters = sorted(main["batter"].unique())
bowlers = sorted(main["bowler"].unique())

col1, col2 = st.columns(2)
batter = col1.selectbox("Batter", batters, index=batters.index("V Kohli") if "V Kohli" in batters else 0)
bowler = col2.selectbox("Bowler", bowlers, index=bowlers.index("JJ Bumrah") if "JJ Bumrah" in bowlers else 0)

batter_team = canonical_team_name(main.loc[main["batter"] == batter].sort_values("date")["batting_team"].iloc[-1])
bowler_team = canonical_team_name(main.loc[main["bowler"] == bowler].sort_values("date")["bowling_team"].iloc[-1])
render_matchup_banner(
    batter, team_color(batter_team), f"Batter · {batter_team}", player_photos.get(batter_name_to_id.get(batter)),
    bowler, team_color(bowler_team), f"Bowler · {bowler_team}", player_photos.get(bowler_name_to_id.get(bowler)),
)

matchup = main[(main["batter"] == batter) & (main["bowler"] == bowler)]
faced = matchup[matchup["extra_wides"] == 0]

st.divider()

if faced.empty:
    st.info(f"{batter} and {bowler} have never faced each other in this dataset.")
else:
    balls_faced = len(faced)
    runs = int(faced["runs_batter"].sum())
    dismissals = int((matchup["player_dismissed"] == batter).sum())
    dot_pct = (faced["runs_batter"] == 0).mean() * 100
    boundary_pct = faced["runs_batter"].isin([4, 6]).mean() * 100
    sixes = int((faced["runs_batter"] == 6).sum())
    average = runs / dismissals if dismissals > 0 else float("nan")
    strike_rate = runs / balls_faced * 100

    cols = st.columns(7)
    cols[0].metric("Balls Faced", balls_faced)
    cols[1].metric("Runs", runs)
    cols[2].metric("Dismissals", dismissals)
    cols[3].metric("Average", f"{average:.1f}" if pd.notna(average) else "—")
    cols[4].metric("Strike Rate", f"{strike_rate:.1f}")
    cols[5].metric("Dot Ball %", f"{dot_pct:.0f}%")
    cols[6].metric("Boundary %", f"{boundary_pct:.0f}%")

    with chart_card("Outcome Distribution", f"{batter} vs {bowler} — result of every ball faced"):
        # A ball where the batter got out is classified as "Wicket" only, never
        # also as its run value, so percentages below sum to 100%.
        own_dismissal = faced["player_dismissed"] == batter
        scoring_balls = faced.loc[~own_dismissal, "runs_batter"]
        outcome_counts = scoring_balls.value_counts().reindex([0, 1, 2, 3, 4, 6], fill_value=0)
        outcome_counts["W"] = int(own_dismissal.sum())
        outcome_labels = ["Dot", "1 Run", "2 Runs", "3 Runs", "Four", "Six", "Wicket"]
        outcome_colors = ["#4B5372", "#3B82F6", "#60A5FA", "#93C5FD", "#22C55E", "#A855F7", "#EF4444"]

        nonzero = outcome_counts.values > 0
        fig = go.Figure(
            go.Pie(
                labels=[l for l, keep in zip(outcome_labels, nonzero) if keep],
                values=[v for v, keep in zip(outcome_counts.values, nonzero) if keep],
                marker=dict(colors=[c for c, keep in zip(outcome_colors, nonzero) if keep], line=dict(color="#0A0E27", width=2)),
                hole=0.62,
                textinfo="label+percent",
                textfont=dict(color="white", size=12),
                hovertemplate="%{label}: %{value} balls (%{percent})<extra></extra>",
                sort=False,
            )
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", height=340, margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
            annotations=[
                dict(
                    text=f"{balls_faced}<br><span style='font-size:11px;color:#8892C0'>balls</span>",
                    x=0.5, y=0.5, font=dict(color="white", size=24), showarrow=False,
                )
            ],
        )
        st.plotly_chart(fig, width="stretch")

    with st.expander("Ball-by-ball history"):
        st.dataframe(
            matchup[["date", "match_id", "over", "ball", "runs_batter", "runs_total", "is_wicket", "dismissal_kind"]],
            width="stretch",
            hide_index=True,
        )
