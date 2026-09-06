"""Career batting statistics per player (blueprint section 28)."""

import numpy as np
import pandas as pd


def _innings_runs(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Runs scored by each player in each (match_id, innings) they batted in."""
    return (
        deliveries.groupby(["batter_id", "batter", "match_id", "innings"])["runs_batter"]
        .sum()
        .reset_index(name="innings_runs")
    )


def _phase_strike_rates(deliveries: pd.DataFrame) -> pd.DataFrame:
    faced = deliveries[deliveries["extra_wides"] == 0]
    phase_agg = (
        faced.groupby(["batter_id", "phase"])
        .agg(runs=("runs_batter", "sum"), balls=("runs_batter", "size"))
        .reset_index()
    )
    phase_agg["strike_rate"] = np.where(
        phase_agg["balls"] > 0, phase_agg["runs"] / phase_agg["balls"] * 100, np.nan
    )
    wide = phase_agg.pivot(index="batter_id", columns="phase", values="strike_rate")
    wide = wide.rename(columns={p: f"strike_rate_{p}" for p in wide.columns})
    return wide.reset_index()


def compute_dismissal_breakdown(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Long-format table: player_id, dismissal_kind, count — how a player
    has been out across their career. Kept separate from compute_batting_stats
    rather than pivoted into wide columns, since most players only have 2-4
    of the ~9 dismissal kinds and a wide table would be mostly empty cells."""
    main = deliveries[~deliveries["is_super_over"]]
    breakdown = (
        main.dropna(subset=["player_dismissed_id"])
        .groupby(["player_dismissed_id", "dismissal_kind"])
        .size()
        .reset_index(name="count")
        .rename(columns={"player_dismissed_id": "player_id"})
    )
    return breakdown.sort_values(["player_id", "count"], ascending=[True, False]).reset_index(drop=True)


def compute_batting_stats(deliveries: pd.DataFrame) -> pd.DataFrame:
    """One row per player_id with career batting figures.

    Excludes super-over deliveries from career aggregates (they're a
    separate tie-breaker format, not regular-innings batting).
    """
    main = deliveries[~deliveries["is_super_over"]]
    faced = main[main["extra_wides"] == 0]  # wides aren't faced by the batter

    innings_runs = _innings_runs(main)

    innings_count = (
        faced.drop_duplicates(subset=["batter_id", "match_id", "innings"])
        .groupby("batter_id")
        .size()
        .rename("innings")
    )

    runs = faced.groupby("batter_id")["runs_batter"].sum().rename("runs")
    balls_faced = faced.groupby("batter_id").size().rename("balls_faced")
    dots = faced[faced["runs_batter"] == 0].groupby("batter_id").size().rename("dot_balls")
    ones = faced[faced["runs_batter"] == 1].groupby("batter_id").size().rename("ones")
    twos = faced[faced["runs_batter"] == 2].groupby("batter_id").size().rename("twos")
    threes = faced[faced["runs_batter"] == 3].groupby("batter_id").size().rename("threes")
    fours = faced[faced["runs_batter"] == 4].groupby("batter_id").size().rename("fours")
    # All-run 5s: rare (74 in the whole dataset) but real — usually an
    # overthrow credited to the batter — and needed so ones..sixes
    # reconciles exactly against total runs.
    fives = faced[faced["runs_batter"] == 5].groupby("batter_id").size().rename("fives")
    sixes = faced[faced["runs_batter"] == 6].groupby("batter_id").size().rename("sixes")

    dismissals = (
        main.dropna(subset=["player_dismissed_id"])
        .groupby("player_dismissed_id")
        .size()
        .rename("dismissals")
    )
    dismissals.index.name = "batter_id"

    fifties = innings_runs[(innings_runs["innings_runs"] >= 50) & (innings_runs["innings_runs"] < 100)]
    fifties = fifties.groupby("batter_id").size().rename("fifties")
    hundreds = innings_runs[innings_runs["innings_runs"] >= 100].groupby("batter_id").size().rename("hundreds")

    names = main[["batter_id", "batter"]].drop_duplicates(subset="batter_id").set_index("batter_id")["batter"]
    names.name = "player_name"

    stats = pd.concat(
        [names, innings_count, runs, balls_faced, dots, ones, twos, threes, fours, fives, sixes, dismissals, fifties, hundreds],
        axis=1,
    ).fillna(0)

    count_cols = [
        "innings", "runs", "balls_faced", "dot_balls", "ones", "twos", "threes",
        "fours", "fives", "sixes", "dismissals", "fifties", "hundreds",
    ]
    for col in count_cols:
        stats[col] = stats[col].astype(int)

    stats["batting_average"] = np.where(
        stats["dismissals"] > 0, stats["runs"] / stats["dismissals"], np.nan
    )
    stats["strike_rate"] = np.where(
        stats["balls_faced"] > 0, stats["runs"] / stats["balls_faced"] * 100, np.nan
    )
    stats["boundary_pct"] = np.where(
        stats["balls_faced"] > 0, (stats["fours"] + stats["sixes"]) / stats["balls_faced"] * 100, np.nan
    )
    stats["dot_ball_pct"] = np.where(
        stats["balls_faced"] > 0, stats["dot_balls"] / stats["balls_faced"] * 100, np.nan
    )
    stats["runs_from_boundaries_pct"] = np.where(
        stats["runs"] > 0, (stats["fours"] * 4 + stats["sixes"] * 6) / stats["runs"] * 100, np.nan
    )

    stats = stats.reset_index().rename(columns={"index": "batter_id"})
    stats = stats.merge(_phase_strike_rates(main), on="batter_id", how="left")
    stats = stats.rename(columns={"batter_id": "player_id"})

    return stats.sort_values("runs", ascending=False).reset_index(drop=True)
