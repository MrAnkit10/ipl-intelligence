"""Career bowling statistics per player (blueprint section 28)."""

import numpy as np
import pandas as pd

# Dismissals credited to the bowler; run outs, retirements and obstructing
# the field are not.
BOWLER_CREDITED_DISMISSALS = {"caught", "bowled", "lbw", "caught and bowled", "stumped", "hit wicket"}


def _phase_economy(legal: pd.DataFrame) -> pd.DataFrame:
    phase_agg = (
        legal.groupby(["bowler_id", "phase"])
        .agg(runs=("bowler_runs", "sum"), balls=("bowler_runs", "size"))
        .reset_index()
    )
    phase_agg["economy"] = np.where(
        phase_agg["balls"] > 0, phase_agg["runs"] / phase_agg["balls"] * 6, np.nan
    )
    wide = phase_agg.pivot(index="bowler_id", columns="phase", values="economy")
    wide = wide.rename(columns={p: f"economy_{p}" for p in wide.columns})
    return wide.reset_index()


def compute_bowling_stats(deliveries: pd.DataFrame) -> pd.DataFrame:
    """One row per player_id with career bowling figures.

    Excludes super-over deliveries from career aggregates, matching
    compute_batting_stats.
    """
    main = deliveries[~deliveries["is_super_over"]].copy()
    legal = main[(main["extra_wides"] == 0) & (main["extra_noballs"] == 0)].copy()
    # Runs charged to the bowler: off the bat plus wides/no-balls, excluding byes/leg-byes/penalty.
    main["bowler_runs"] = main["runs_batter"] + main["extra_wides"] + main["extra_noballs"]
    legal["bowler_runs"] = legal["runs_batter"]

    names = main[["bowler_id", "bowler"]].drop_duplicates(subset="bowler_id").set_index("bowler_id")["bowler"]
    names.name = "player_name"

    balls_bowled = legal.groupby("bowler_id").size().rename("balls_bowled")
    runs_conceded = main.groupby("bowler_id")["bowler_runs"].sum().rename("runs_conceded")

    bowler_wickets = main[main["dismissal_kind"].isin(BOWLER_CREDITED_DISMISSALS)]
    wickets = bowler_wickets.groupby("bowler_id").size().rename("wickets")

    dots = legal[legal["bowler_runs"] == 0].groupby("bowler_id").size().rename("dot_balls")
    boundaries_conceded = (
        legal[legal["runs_batter"].isin([4, 6])].groupby("bowler_id").size().rename("boundaries_conceded")
    )

    stats = pd.concat([names, balls_bowled, runs_conceded, wickets, dots, boundaries_conceded], axis=1).fillna(0)
    for col in ["balls_bowled", "runs_conceded", "wickets", "dot_balls", "boundaries_conceded"]:
        stats[col] = stats[col].astype(int)

    stats["overs"] = (stats["balls_bowled"] // 6) + (stats["balls_bowled"] % 6) / 10
    stats["economy"] = np.where(
        stats["balls_bowled"] > 0, stats["runs_conceded"] / stats["balls_bowled"] * 6, np.nan
    )
    stats["bowling_average"] = np.where(
        stats["wickets"] > 0, stats["runs_conceded"] / stats["wickets"], np.nan
    )
    stats["bowling_strike_rate"] = np.where(
        stats["wickets"] > 0, stats["balls_bowled"] / stats["wickets"], np.nan
    )
    stats["dot_ball_pct"] = np.where(
        stats["balls_bowled"] > 0, stats["dot_balls"] / stats["balls_bowled"] * 100, np.nan
    )
    stats["boundary_conceded_pct"] = np.where(
        stats["balls_bowled"] > 0, stats["boundaries_conceded"] / stats["balls_bowled"] * 100, np.nan
    )

    stats = stats.reset_index().rename(columns={"index": "bowler_id"})
    stats = stats.merge(_phase_economy(legal), on="bowler_id", how="left")
    stats = stats.rename(columns={"bowler_id": "player_id"})

    return stats.sort_values("wickets", ascending=False).reset_index(drop=True)
