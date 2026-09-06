"""Tournament-wide headline numbers for the Module 1 overview dashboard."""

import pandas as pd


def compute_overview(matches: pd.DataFrame, deliveries: pd.DataFrame, batting_stats: pd.DataFrame,
                      bowling_stats: pd.DataFrame) -> dict:
    main = deliveries[~deliveries["is_super_over"]]

    # Highest/lowest totals are conventionally reported for completed innings
    # only; rain-abandoned "no result" matches can end after just a handful
    # of balls and would otherwise dominate the "lowest total" figure.
    decided_match_ids = matches.loc[matches["outcome_type"] != "no_result", "match_id"]
    innings_totals = (
        main[main["match_id"].isin(decided_match_ids)].groupby(["match_id", "innings"])["runs_total"].sum()
    )

    top_batter = batting_stats.iloc[0]
    top_bowler = bowling_stats.iloc[0]

    return {
        "seasons": f"{matches['season_year'].min()}-{matches['season_year'].max()}",
        "matches_played": len(matches),
        "total_runs": int(main["runs_total"].sum()),
        "total_wickets": int(main["is_wicket"].sum()),
        "total_sixes": int((main["runs_batter"] == 6).sum()),
        "total_fours": int((main["runs_batter"] == 4).sum()),
        "highest_total": int(innings_totals.max()),
        "lowest_total": int(innings_totals.min()),
        "top_run_scorer": f"{top_batter['player_name']} ({top_batter['runs']} runs)",
        "leading_wicket_taker": f"{top_bowler['player_name']} ({top_bowler['wickets']} wickets)",
    }


def print_overview(overview: dict) -> None:
    width = max(len(k) for k in overview) + 2
    for key, value in overview.items():
        label = key.replace("_", " ").title()
        print(f"{label:<{width + 10}}{value}")


if __name__ == "__main__":
    from pathlib import Path

    processed = Path(__file__).resolve().parents[2] / "data" / "processed"
    matches = pd.read_parquet(processed / "matches.parquet")
    deliveries = pd.read_parquet(processed / "deliveries.parquet")
    batting_stats = pd.read_csv(processed / "batting_stats.csv")
    bowling_stats = pd.read_csv(processed / "bowling_stats.csv")

    print_overview(compute_overview(matches, deliveries, batting_stats, bowling_stats))
