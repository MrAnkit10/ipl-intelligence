"""Reconstruct a traditional batting/bowling scorecard for one match from
ball-by-ball data — the same information a scorecard on any cricket site
shows, derived directly from Cricsheet rather than a separate source."""

from __future__ import annotations

import pandas as pd

BOWLER_CREDITED_DISMISSALS = {"caught", "bowled", "lbw", "caught and bowled", "stumped", "hit wicket"}

DISMISSAL_TEMPLATES = {
    "bowled": "b {bowler}",
    "lbw": "lbw b {bowler}",
    "caught and bowled": "c & b {bowler}",
    "caught": "c {fielder} b {bowler}",
    "stumped": "st {fielder} b {bowler}",
    "run out": "run out ({fielder})",
    "hit wicket": "hit wicket b {bowler}",
    "retired hurt": "retired hurt",
    "retired out": "retired out",
    "obstructing the field": "obstructing the field",
}


def _dismissal_text(kind: str, bowler: str, fielders: str | None) -> str:
    fielder = (fielders or "").split(";")[0] or "sub"
    template = DISMISSAL_TEMPLATES.get(kind, kind)
    return template.format(bowler=bowler, fielder=fielder)


def _batting_order(innings_deliveries: pd.DataFrame) -> pd.DataFrame:
    """Rank batters by the delivery_id they first appear at (as batter or
    non-striker), so both openers rank 1-2 even though only one faces ball 1."""
    appearances = pd.concat(
        [
            innings_deliveries[["delivery_id", "batter_id", "batter"]].rename(
                columns={"batter_id": "player_id", "batter": "player_name"}
            ),
            innings_deliveries[["delivery_id", "non_striker_id", "non_striker"]].rename(
                columns={"non_striker_id": "player_id", "non_striker": "player_name"}
            ),
        ],
        ignore_index=True,
    )
    first_seen = appearances.groupby(["player_id", "player_name"])["delivery_id"].min().reset_index()
    return first_seen.sort_values("delivery_id").reset_index(drop=True)


def compute_innings_scorecard(innings_deliveries: pd.DataFrame) -> dict:
    faced = innings_deliveries[innings_deliveries["extra_wides"] == 0]
    order = _batting_order(innings_deliveries)

    batting_rows = []
    for _, p in order.iterrows():
        player_balls = faced[faced["batter_id"] == p["player_id"]]
        if player_balls.empty and not (innings_deliveries["batter_id"] == p["player_id"]).any():
            continue  # never actually came to the crease as a batter (only ever non-striker)
        runs = int(player_balls["runs_batter"].sum())
        balls = len(player_balls)
        fours = int((player_balls["runs_batter"] == 4).sum())
        sixes = int((player_balls["runs_batter"] == 6).sum())
        dismissal = innings_deliveries[innings_deliveries["player_dismissed_id"] == p["player_id"]]
        if dismissal.empty:
            how_out = "not out"
        else:
            d = dismissal.iloc[0]
            how_out = _dismissal_text(d["dismissal_kind"], d["bowler"], d["fielders"])
        batting_rows.append(
            {
                "batter": p["player_name"],
                "how_out": how_out,
                "runs": runs,
                "balls": balls,
                "fours": fours,
                "sixes": sixes,
                "strike_rate": round(runs / balls * 100, 1) if balls > 0 else 0.0,
            }
        )

    legal = innings_deliveries[(innings_deliveries["extra_wides"] == 0) & (innings_deliveries["extra_noballs"] == 0)]
    bowling_rows = []
    for bowler, group in innings_deliveries.groupby("bowler", sort=False):
        legal_balls = legal[legal["bowler"] == bowler]
        overs_bowled = sorted(legal_balls["over"].unique())
        maidens = sum(
            1 for o in overs_bowled if legal_balls.loc[legal_balls["over"] == o, "runs_total"].sum() == 0
        )
        runs_conceded = int((group["runs_batter"] + group["extra_wides"] + group["extra_noballs"]).sum())
        wickets = int(group["dismissal_kind"].isin(BOWLER_CREDITED_DISMISSALS).sum())
        balls_bowled = len(legal_balls)
        bowling_rows.append(
            {
                "bowler": bowler,
                "overs": f"{balls_bowled // 6}.{balls_bowled % 6}",
                "maidens": maidens,
                "runs": runs_conceded,
                "wickets": wickets,
                "economy": round(runs_conceded / balls_bowled * 6, 2) if balls_bowled > 0 else 0.0,
            }
        )
    # First-appearance order, matching how the innings actually unfolded.
    bowler_order = innings_deliveries.drop_duplicates("bowler")["bowler"].tolist()
    bowling_rows.sort(key=lambda r: bowler_order.index(r["bowler"]))

    total_runs = int(innings_deliveries["runs_total"].sum())
    total_wickets = int(innings_deliveries["is_wicket"].sum())
    legal_balls_total = len(legal)
    extras = {
        "wides": int(innings_deliveries["extra_wides"].sum()),
        "no_balls": int(innings_deliveries["extra_noballs"].sum()),
        "byes": int(innings_deliveries["extra_byes"].sum()),
        "leg_byes": int(innings_deliveries["extra_legbyes"].sum()),
        "penalty": int(innings_deliveries["extra_penalty"].sum()),
    }

    fall_of_wickets = []
    cum_runs, cum_wickets = 0, 0
    for _, row in innings_deliveries.sort_values(["over", "ball"]).iterrows():
        cum_runs += int(row["runs_total"])
        if row["is_wicket"]:
            cum_wickets += 1
            fall_of_wickets.append(
                {
                    "wicket_number": cum_wickets,
                    "score": cum_runs,
                    "over": f"{row['over']}.{row['ball']}",
                    "player": row["player_dismissed"],
                }
            )

    return {
        "batting_team": innings_deliveries["batting_team"].iloc[0],
        "total_runs": total_runs,
        "total_wickets": total_wickets,
        "overs": f"{legal_balls_total // 6}.{legal_balls_total % 6}",
        "batting": batting_rows,
        "bowling": bowling_rows,
        "extras": extras,
        "fall_of_wickets": fall_of_wickets,
    }


def compute_match_scorecard(match_id: int, deliveries: pd.DataFrame) -> list[dict]:
    """One dict per innings (excludes super overs — shown separately if present)."""
    match_deliveries = deliveries[(deliveries["match_id"] == match_id) & (~deliveries["is_super_over"])]
    return [
        compute_innings_scorecard(match_deliveries[match_deliveries["innings"] == innings_num])
        for innings_num in sorted(match_deliveries["innings"].unique())
    ]
