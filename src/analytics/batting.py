"""Career batting statistics per player (blueprint section 28)."""

from __future__ import annotations

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
    stats = stats.merge(_innings_extremes(faced, innings_runs), on="batter_id", how="left")
    stats = stats.merge(_batting_first_vs_chase(main), on="batter_id", how="left")
    stats = stats.rename(columns={"batter_id": "player_id"})

    stats["fifty_rate"] = np.where(stats["innings"] > 0, stats["fifties"] / stats["innings"] * 100, np.nan)
    stats["big_score_pct"] = np.where(
        stats["innings"] > 0, (stats["fifties"] + stats["hundreds"]) / stats["innings"] * 100, np.nan
    )
    fifty_plus = stats["fifties"] + stats["hundreds"]
    stats["conversion_pct"] = np.where(fifty_plus > 0, stats["hundreds"] / fifty_plus * 100, np.nan)
    boundaries = stats["fours"] + stats["sixes"]
    stats["balls_per_boundary"] = np.where(boundaries > 0, stats["balls_faced"] / boundaries, np.nan)
    stats["six_rate"] = np.where(stats["balls_faced"] > 0, stats["sixes"] / stats["balls_faced"] * 100, np.nan)
    stats["acceleration"] = np.where(
        stats["strike_rate_middle"] > 0, stats["strike_rate_death"] / stats["strike_rate_middle"], np.nan
    )

    return stats.sort_values("runs", ascending=False).reset_index(drop=True)


def _innings_extremes(faced: pd.DataFrame, innings_runs: pd.DataFrame) -> pd.DataFrame:
    """Per player: matches played, highest single-innings score, and
    debut/last-played dates — the identity-strip facts on a broadcast
    "career dossier" graphic."""
    matches_played = faced.groupby("batter_id")["match_id"].nunique().rename("matches_played")
    highest_score = innings_runs.groupby("batter_id")["innings_runs"].max().rename("highest_score")
    debut = faced.groupby("batter_id")["date"].min().rename("debut_date")
    last_played = faced.groupby("batter_id")["date"].max().rename("last_played_date")
    return pd.concat([matches_played, highest_score, debut, last_played], axis=1).reset_index().rename(
        columns={"index": "batter_id"}
    )


def _batting_first_vs_chase(main: pd.DataFrame) -> pd.DataFrame:
    """Strike rate split by whether the player was batting first (innings 1)
    or chasing (innings 2) — excludes super overs (innings 3+), which are a
    separate tie-breaker format."""
    faced = main[(main["extra_wides"] == 0) & (main["innings"].isin([1, 2]))]
    agg = (
        faced.groupby(["batter_id", "innings"])
        .agg(runs=("runs_batter", "sum"), balls=("runs_batter", "size"))
        .reset_index()
    )
    agg["strike_rate"] = np.where(agg["balls"] > 0, agg["runs"] / agg["balls"] * 100, np.nan)
    wide = agg.pivot(index="batter_id", columns="innings", values="strike_rate")
    wide = wide.rename(columns={1: "batting_first_strike_rate", 2: "chase_strike_rate"})
    return wide.reset_index()


def compute_fielding_stats(deliveries: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    """Career catches per player, derived from dismissal records where
    dismissal_kind is 'caught' or 'caught and bowled' and the named fielder
    matches a known player. Matched by exact name against the Cricsheet
    people register (players.parquet); an unregistered substitute fielder
    (about 4% of catches) is simply not counted rather than guessed at."""
    main = deliveries[~deliveries["is_super_over"]]
    caught = main[main["dismissal_kind"].isin(["caught", "caught and bowled"])].dropna(subset=["fielders"])
    name_to_id = dict(zip(players["register_name"], players["player_id"]))
    caught = caught.assign(fielder_id=caught["fielders"].map(name_to_id))
    catches = (
        caught.dropna(subset=["fielder_id"])
        .groupby("fielder_id")
        .size()
        .rename("catches")
        .reset_index()
        .rename(columns={"fielder_id": "player_id"})
    )
    return catches


PERCENTILE_METRICS = {
    # column -> (display label, group, higher_is_better)
    "boundary_pct": ("Boundary %", "power", True),
    "six_rate": ("Six Rate", "power", True),
    "strike_rate_death": ("Death SR", "power", True),
    "chase_strike_rate": ("Chase SR", "power", True),
    "batting_average": ("Average", "consistency", True),
    "big_score_pct": ("Big Score %", "consistency", True),
    "conversion_pct": ("Conversion", "consistency", True),
    "balls_per_boundary": ("Balls/Bndy", "consistency", False),
    "dot_ball_pct": ("Dot %", "tempo", False),
    "fifty_rate": ("Fifty Rate", "tempo", True),
    "strike_rate_middle": ("Middle SR", "tempo", True),
    "acceleration": ("Acceleration", "tempo", True),
}

GROUP_COLORS = {"power": "#EF4444", "consistency": "#3B82F6", "tempo": "#22C55E"}


def compute_batting_percentiles(batting_stats: pd.DataFrame, min_innings: int = 15) -> pd.DataFrame:
    """Percentile rank (0-100) of every PERCENTILE_METRICS column, computed
    against the pool of players with at least min_innings career innings —
    the same qualification-threshold idea as a real "qualified for the
    average" cricket table, so one nervous 3-ball cameo doesn't distort the
    scale. A player below the threshold is still ranked against that pool
    (never against themselves alone)."""
    pool = batting_stats[batting_stats["innings"] >= min_innings]
    out = batting_stats[["player_id"]].copy()
    for col, (_, _, higher_is_better) in PERCENTILE_METRICS.items():
        values = pool[col].dropna()
        if values.empty:
            out[col] = np.nan
            continue
        ranks = batting_stats[col].apply(
            lambda v, values=values: np.nan if pd.isna(v) else (values <= v).mean() * 100
        )
        out[col] = ranks if higher_is_better else 100 - ranks
    return out
