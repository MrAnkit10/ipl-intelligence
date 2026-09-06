"""Records & Milestones: biggest wins, highest/lowest totals, best
partnerships, and fastest fifties/hundreds — classic cricket "records
page" content, all derived directly from Cricsheet ball-by-ball data.
"""

from __future__ import annotations

import pandas as pd


def compute_biggest_wins(matches: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    decided = matches[matches["outcome_type"] == "win"].copy()

    by_runs = decided.dropna(subset=["win_by_runs"]).sort_values("win_by_runs", ascending=False).head(top_n)
    by_runs = by_runs.assign(margin_type="runs", margin_value=by_runs["win_by_runs"])

    by_wickets = decided.dropna(subset=["win_by_wickets"]).sort_values("win_by_wickets", ascending=False).head(top_n)
    by_wickets = by_wickets.assign(margin_type="wickets", margin_value=by_wickets["win_by_wickets"])

    cols = ["match_id", "date", "venue", "team1", "team2", "winner", "margin_type", "margin_value"]
    return pd.concat([by_runs[cols], by_wickets[cols]], ignore_index=True)


def _innings_totals(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    main = deliveries[~deliveries["is_super_over"]]
    totals = (
        main.groupby(["match_id", "innings", "batting_team", "bowling_team"])
        .agg(total_runs=("runs_total", "sum"), wickets=("is_wicket", "sum"))
        .reset_index()
    )
    return totals.merge(matches[["match_id", "date", "venue"]], on="match_id", how="left")


def compute_team_totals(matches: pd.DataFrame, deliveries: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    totals = _innings_totals(matches, deliveries)

    highest = totals.sort_values("total_runs", ascending=False).head(top_n).assign(category="highest")
    # "Lowest total" only means something for a completed innings (all out) -
    # a low score cut short by rain isn't a batting-collapse record.
    all_out = totals[totals["wickets"] >= 10]
    lowest = all_out.sort_values("total_runs", ascending=True).head(top_n).assign(category="lowest")

    cols = ["match_id", "date", "venue", "batting_team", "bowling_team", "total_runs", "wickets", "category"]
    return pd.concat([highest[cols], lowest[cols]], ignore_index=True)


def compute_partnerships(matches: pd.DataFrame, deliveries: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Best partnerships by runs, for any wicket. A partnership is the span
    of balls between one wicket falling and the next (or innings end),
    identified by the number of wickets already down when it starts —
    the standard "1st wicket partnership" (opening pair), "2nd wicket
    partnership", etc."""
    main = deliveries[~deliveries["is_super_over"]].sort_values(["match_id", "innings", "over", "ball"]).copy()
    main["wickets_before"] = main.groupby(["match_id", "innings"])["is_wicket"].transform(
        lambda s: s.cumsum().shift(fill_value=0)
    )

    rows = []
    for (match_id, innings), group in main.groupby(["match_id", "innings"]):
        for wickets_before, partnership in group.groupby("wickets_before"):
            batters = pd.unique(partnership[["batter", "non_striker"]].values.ravel())
            if len(batters) != 2:
                continue
            runs = int(partnership["runs_total"].sum())
            balls = int((partnership["extra_wides"] == 0).sum())
            rows.append(
                {
                    "match_id": match_id,
                    "innings": innings,
                    "batting_team": partnership["batting_team"].iloc[0],
                    "wicket_number": int(wickets_before) + 1,
                    "batter1": batters[0],
                    "batter2": batters[1],
                    "runs": runs,
                    "balls": balls,
                }
            )

    partnerships = pd.DataFrame(rows)
    partnerships = partnerships.merge(matches[["match_id", "date", "venue"]], on="match_id", how="left")
    return partnerships.sort_values("runs", ascending=False).head(top_n).reset_index(drop=True)


def _balls_to_milestone(faced: pd.DataFrame, milestone: int) -> pd.DataFrame:
    """For each innings that reached `milestone` runs, the number of balls
    faced to get there — "fastest fifty/hundred" means balls to REACH the
    milestone, not total balls in the whole innings (a player can reach
    100 in 30 balls and then bat on for 40 more balls scoring further
    runs; the innings-total balls-faced is a different, slower number)."""
    ordered = faced.sort_values(["match_id", "innings", "over", "ball"]).copy()
    ordered["ball_rank"] = ordered.groupby(["match_id", "batter_id"]).cumcount() + 1
    ordered["cum_runs"] = ordered.groupby(["match_id", "batter_id"])["runs_batter"].cumsum()

    reached = ordered[ordered["cum_runs"] >= milestone]
    first_ball = reached.groupby(["match_id", "batter_id"]).cumcount() == 0
    milestone_balls = reached[first_ball][["match_id", "batter_id", "ball_rank"]].copy()
    return milestone_balls.rename(columns={"ball_rank": "balls_to_milestone"})


def compute_batting_extremes(matches: pd.DataFrame, deliveries: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Fastest fifties/hundreds (balls to reach the milestone) and most
    sixes/fours in a single innings — single-innings milestones, distinct
    from the career totals already in batting_stats.csv."""
    main = deliveries[~deliveries["is_super_over"]]
    faced = main[main["extra_wides"] == 0]

    per_innings = (
        faced.groupby(["match_id", "batter_id", "batter", "batting_team", "bowling_team"])
        .agg(
            runs=("runs_batter", "sum"),
            balls_faced=("runs_batter", "size"),
            fours=("runs_batter", lambda s: (s == 4).sum()),
            sixes=("runs_batter", lambda s: (s == 6).sum()),
        )
        .reset_index()
        .merge(matches[["match_id", "date", "venue"]], on="match_id", how="left")
    )

    fifty_balls = _balls_to_milestone(faced, 50)[["match_id", "batter_id", "balls_to_milestone"]]
    hundred_balls = _balls_to_milestone(faced, 100)[["match_id", "batter_id", "balls_to_milestone"]]

    fastest_fifty = (
        per_innings.merge(fifty_balls, on=["match_id", "batter_id"])
        .sort_values("balls_to_milestone")
        .head(top_n)
        .assign(category="fastest_fifty")
    )
    fastest_hundred = (
        per_innings.merge(hundred_balls, on=["match_id", "batter_id"])
        .sort_values("balls_to_milestone")
        .head(top_n)
        .assign(category="fastest_hundred")
    )
    most_sixes = per_innings.sort_values("sixes", ascending=False).head(top_n).assign(
        category="most_sixes", balls_to_milestone=None
    )
    most_fours = per_innings.sort_values("fours", ascending=False).head(top_n).assign(
        category="most_fours", balls_to_milestone=None
    )

    cols = [
        "match_id", "date", "venue", "batter_id", "batter", "batting_team", "bowling_team",
        "runs", "balls_faced", "balls_to_milestone", "fours", "sixes", "category",
    ]
    return pd.concat([fastest_fifty[cols], fastest_hundred[cols], most_sixes[cols], most_fours[cols]], ignore_index=True)
