"""Sanity checks on the parsed matches/deliveries/players tables.

This is step 6 of the blueprint's "What to Build First": validate before
building anything downstream. Raises AssertionError on the first failed
check so problems can't silently propagate into features or models.

Usage:
    python -m src.data.validate_data
"""

from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def load_tables():
    matches = pd.read_parquet(PROCESSED_DIR / "matches.parquet")
    deliveries = pd.read_parquet(PROCESSED_DIR / "deliveries.parquet")
    players = pd.read_parquet(PROCESSED_DIR / "players.parquet")
    return matches, deliveries, players


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, f"Validation failed: {label}"


def run_checks(matches: pd.DataFrame, deliveries: pd.DataFrame, players: pd.DataFrame) -> None:
    check("matches.match_id is unique", matches["match_id"].is_unique)
    check("deliveries.delivery_id is unique", deliveries["delivery_id"].is_unique)
    check("no matches with null date", matches["date"].notna().all())
    check("no matches with null venue", matches["venue"].notna().all())
    check(
        "every delivery.match_id exists in matches",
        deliveries["match_id"].isin(matches["match_id"]).all(),
    )
    check(
        "runs_total equals runs_batter + runs_extras",
        (deliveries["runs_total"] == deliveries["runs_batter"] + deliveries["runs_extras"]).all(),
    )
    check(
        "runs_extras equals sum of extras sub-columns",
        (
            deliveries["runs_extras"]
            == deliveries[["extra_wides", "extra_noballs", "extra_byes", "extra_legbyes", "extra_penalty"]].sum(
                axis=1
            )
        ).all(),
    )
    check("is_wicket is 0/1 only", set(deliveries["is_wicket"].unique()) <= {0, 1})
    check(
        "player_dismissed set exactly when is_wicket == 1",
        (deliveries["is_wicket"] == deliveries["player_dismissed"].notna()).all(),
    )
    check("ball number is always >= 1", (deliveries["ball"] >= 1).all())
    check(
        "resolved matches (outcome_type == 'win') have a winner that is one of the two teams",
        matches.loc[matches["outcome_type"] == "win"]
        .apply(lambda r: r["winner"] in (r["team1"], r["team2"]), axis=1)
        .all(),
    )
    check("players.player_id is unique", players["player_id"].is_unique)
    check("players has no null player_id", players["player_id"].notna().all())

    balls_per_match_innings = (
        deliveries.groupby(["match_id", "innings"]).size().rename("n_balls").reset_index()
    )
    check(
        "every (match, innings) has at least 1 ball bowled",
        (balls_per_match_innings["n_balls"] > 0).all(),
    )

    season_range = (matches["season_year"].min(), matches["season_year"].max())
    print(f"Seasons covered: {season_range[0]}-{season_range[1]}")
    print(f"Matches: {len(matches):,} | Deliveries: {len(deliveries):,} | Players: {len(players):,}")


def main() -> None:
    matches, deliveries, players = load_tables()
    run_checks(matches, deliveries, players)
    print("\nAll validation checks passed.")


if __name__ == "__main__":
    main()
