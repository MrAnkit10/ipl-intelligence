"""Career bowling statistics per player (blueprint section 28)."""

from __future__ import annotations

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


def _best_bowling_figures(main: pd.DataFrame) -> pd.DataFrame:
    """Best single-innings bowling figures per career — the "4/25" a
    scorecard shows. Aggregates each (bowler, match) to its wicket count
    and runs conceded, then ranks by the standard cricket convention:
    most wickets first, fewest runs conceded as the tiebreak. Requires
    main["bowler_runs"] to already be set by the caller."""
    bowler_wickets = main[main["dismissal_kind"].isin(BOWLER_CREDITED_DISMISSALS)]
    per_match_wickets = bowler_wickets.groupby(["bowler_id", "match_id"]).size().rename("wickets")
    per_match_runs = main.groupby(["bowler_id", "match_id"])["bowler_runs"].sum().rename("runs")
    per_match = pd.concat([per_match_wickets, per_match_runs], axis=1)
    per_match["wickets"] = per_match["wickets"].fillna(0).astype(int)
    per_match = per_match.reset_index().sort_values(["wickets", "runs"], ascending=[False, True])
    best = per_match.groupby("bowler_id").first()
    return best.rename(
        columns={"wickets": "best_bowling_wickets", "runs": "best_bowling_runs", "match_id": "best_bowling_match_id"}
    ).reset_index()


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
    stats = stats.merge(_best_bowling_figures(main), on="bowler_id", how="left")
    stats = stats.merge(_bowling_career_span(main), on="bowler_id", how="left")
    stats = stats.rename(columns={"bowler_id": "player_id"})

    stats["best_bowling_figures"] = stats.apply(
        lambda r: f"{int(r['best_bowling_wickets'])}/{int(r['best_bowling_runs'])}"
        if pd.notna(r["best_bowling_wickets"]) else None,
        axis=1,
    )
    stats["wickets_per_match"] = np.where(
        stats["matches_played"] > 0, stats["wickets"] / stats["matches_played"], np.nan
    )

    return stats.sort_values("wickets", ascending=False).reset_index(drop=True)


def _bowling_career_span(main: pd.DataFrame) -> pd.DataFrame:
    """Matches played and debut/last-played dates, for the same identity
    strip treatment batting_stats gets from _innings_extremes."""
    matches_played = main.groupby("bowler_id")["match_id"].nunique().rename("matches_played")
    debut = main.groupby("bowler_id")["date"].min().rename("debut_date")
    last_played = main.groupby("bowler_id")["date"].max().rename("last_played_date")
    return pd.concat([matches_played, debut, last_played], axis=1).reset_index().rename(
        columns={"index": "bowler_id"}
    )


BOWLING_PERCENTILE_METRICS = {
    # column -> (display label, group, higher_is_better)
    "wickets_per_match": ("Wkts/Match", "impact", True),
    "best_bowling_wickets": ("Best Bowling", "impact", True),
    "bowling_strike_rate": ("Strike Rate", "impact", False),
    "economy": ("Economy", "economy", False),
    "economy_powerplay": ("Powerplay Econ", "economy", False),
    "economy_death": ("Death Econ", "economy", False),
    "dot_ball_pct": ("Dot %", "control", True),
    "boundary_conceded_pct": ("Boundary %", "control", False),
    "bowling_average": ("Average", "control", False),
}

BOWLING_GROUP_COLORS = {"impact": "#EF4444", "economy": "#3B82F6", "control": "#22C55E"}


def compute_bowling_percentiles(bowling_stats: pd.DataFrame, min_balls: int = 300) -> pd.DataFrame:
    """Percentile rank (0-100) of every BOWLING_PERCENTILE_METRICS column,
    against the pool of bowlers with at least min_balls career balls
    bowled (~50 overs) - the same qualification-threshold idea as
    compute_batting_percentiles, so a two-over cameo doesn't distort the
    scale."""
    pool = bowling_stats[bowling_stats["balls_bowled"] >= min_balls]
    out = bowling_stats[["player_id"]].copy()
    for col, (_, _, higher_is_better) in BOWLING_PERCENTILE_METRICS.items():
        values = pool[col].dropna()
        if values.empty:
            out[col] = np.nan
            continue
        ranks = bowling_stats[col].apply(
            lambda v, values=values: np.nan if pd.isna(v) else (values <= v).mean() * 100
        )
        out[col] = ranks if higher_is_better else 100 - ranks
    return out
