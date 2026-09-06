import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.data_loader import load_deliveries

st.set_page_config(page_title="Batter vs Bowler | IPL Intelligence", page_icon="⚔️", layout="wide")
st.title("⚔️ Batter vs Bowler Matchup")
st.caption(
    "Historical head-to-head from ball-by-ball data. A model-based next-ball outcome "
    "distribution (blueprint Module 5) is a planned multiclass-classification extension, "
    "not yet built."
)

deliveries = load_deliveries()
main = deliveries[~deliveries["is_super_over"]]

batters = sorted(main["batter"].unique())
bowlers = sorted(main["bowler"].unique())

col1, col2 = st.columns(2)
batter = col1.selectbox("Batter", batters, index=batters.index("V Kohli") if "V Kohli" in batters else 0)
bowler = col2.selectbox("Bowler", bowlers, index=bowlers.index("JJ Bumrah") if "JJ Bumrah" in bowlers else 0)

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

    st.subheader("Outcome Distribution")
    # A ball where the batter got out is classified as "Wicket" only, never
    # also as its run value, so percentages below sum to 100%.
    own_dismissal = faced["player_dismissed"] == batter
    scoring_balls = faced.loc[~own_dismissal, "runs_batter"]
    outcome_counts = scoring_balls.value_counts().reindex([0, 1, 2, 3, 4, 6], fill_value=0)
    outcome_counts["W"] = int(own_dismissal.sum())
    outcome_df = pd.DataFrame(
        {"outcome": ["Dot", "1 Run", "2 Runs", "3 Runs", "Four", "Six", "Wicket"], "count": outcome_counts.values}
    )
    outcome_df["pct"] = outcome_df["count"] / balls_faced * 100
    fig = px.bar(outcome_df, x="outcome", y="pct", text="pct", title=f"{batter} vs {bowler}: outcome % per ball")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(fig, width="stretch")

    with st.expander("Ball-by-ball history"):
        st.dataframe(
            matchup[["date", "match_id", "over", "ball", "runs_batter", "runs_total", "is_wicket", "dismissal_kind"]],
            width="stretch",
            hide_index=True,
        )
