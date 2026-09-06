"""Build the descriptive-analytics and BI-export tables from matches/deliveries.

Writes to data/processed/: batting_stats.csv, bowling_stats.csv,
team_stats.csv, venue_stats.csv, head_to_head.csv, season_trends.csv,
matches_bi.csv, overview_kpis.csv — matching the recommended raw/processed
data structure in the blueprint (section 10), plus the extra tables BI
tools (Tableau, Power BI) need to connect to directly without recomputing
team-name normalization themselves (section 42).

Usage:
    python -m src.analytics.build_stats_tables
"""

from pathlib import Path

import pandas as pd

from src.analytics.batting import (
    compute_batting_percentiles,
    compute_batting_stats,
    compute_dismissal_breakdown,
    compute_fielding_stats,
)
from src.analytics.bowling import compute_bowling_stats
from src.analytics.overview import compute_overview
from src.analytics.team_stats import (
    compute_head_to_head,
    compute_season_trends,
    compute_team_stats,
    compute_venue_stats,
)
from src.data.team_normalization import canonical_team_name
from src.data.venue_normalization import canonical_venue_name

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def compute_player_current_team(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Each player's most recent team, for filtering player tables by team
    in a BI tool (a player's own team when batting is batting_team; when
    bowling it's bowling_team)."""
    appearances = pd.concat(
        [
            deliveries[["batter_id", "batting_team", "date"]].rename(
                columns={"batter_id": "player_id", "batting_team": "team"}
            ),
            deliveries[["bowler_id", "bowling_team", "date"]].rename(
                columns={"bowler_id": "player_id", "bowling_team": "team"}
            ),
        ],
        ignore_index=True,
    ).dropna(subset=["player_id"])
    appearances["team"] = appearances["team"].map(canonical_team_name, na_action="ignore")

    latest = appearances.loc[appearances.groupby("player_id")["date"].idxmax()]
    return latest[["player_id", "team"]].rename(columns={"team": "current_team"}).reset_index(drop=True)


def compute_phase_trends(deliveries: pd.DataFrame) -> pd.DataFrame:
    """League-wide scoring by phase per season (blueprint section 37,
    "Advanced Analytics: Powerplay, middle overs, death overs") — a
    league-level view to complement the per-player phase splits already in
    batting_stats.csv."""
    main = deliveries[~deliveries["is_super_over"]]
    grouped = main.groupby(["season_year", "phase"])
    balls = grouped.size()
    legal_balls = main[(main["extra_wides"] == 0) & (main["extra_noballs"] == 0)].groupby(["season_year", "phase"]).size()

    trends = pd.DataFrame(
        {
            "runs": grouped["runs_total"].sum(),
            "wickets": grouped["is_wicket"].sum(),
            "balls": balls,
            "legal_balls": legal_balls,
            "boundaries": grouped.apply(lambda g: g["runs_batter"].isin([4, 6]).sum()),
        }
    ).reset_index()
    trends["run_rate"] = round(trends["runs"] / trends["legal_balls"] * 6, 2)
    trends["boundary_pct"] = round(trends["boundaries"] / trends["legal_balls"] * 100, 2)
    trends = trends[trends["phase"] != "super_over"]
    return trends.sort_values(["season_year", "phase"]).reset_index(drop=True)


def build_matches_bi(matches: pd.DataFrame) -> pd.DataFrame:
    """matches.parquet plus canonical team columns, for BI tools that
    connect directly to a match-grain table (season trends, toss analysis,
    etc.) without reimplementing the normalization mapping. Original
    columns are kept untouched alongside the new canonical_* ones."""
    matches_bi = matches.copy()
    for col in ["team1", "team2", "toss_winner", "winner"]:
        matches_bi[f"canonical_{col}"] = matches_bi[col].map(canonical_team_name, na_action="ignore")
    matches_bi["canonical_venue"] = matches_bi["venue"].map(canonical_venue_name, na_action="ignore")
    return matches_bi


def main() -> None:
    matches = pd.read_parquet(PROCESSED_DIR / "matches.parquet")
    deliveries = pd.read_parquet(PROCESSED_DIR / "deliveries.parquet")
    players = pd.read_parquet(PROCESSED_DIR / "players.parquet")

    batting_stats = compute_batting_stats(deliveries)
    bowling_stats = compute_bowling_stats(deliveries)
    fielding_stats = compute_fielding_stats(deliveries, players)
    batting_stats = batting_stats.merge(fielding_stats, on="player_id", how="left")
    batting_stats["catches"] = batting_stats["catches"].fillna(0).astype(int)
    batting_percentiles = compute_batting_percentiles(batting_stats)
    team_stats = compute_team_stats(matches)
    venue_stats = compute_venue_stats(matches, deliveries)
    head_to_head = compute_head_to_head(matches)
    season_trends = compute_season_trends(matches, deliveries)
    phase_trends = compute_phase_trends(deliveries)
    dismissal_breakdown = compute_dismissal_breakdown(deliveries)
    matches_bi = build_matches_bi(matches)
    overview_kpis = pd.DataFrame([compute_overview(matches, deliveries, batting_stats, bowling_stats)])

    current_team = compute_player_current_team(deliveries)
    batting_stats = batting_stats.merge(current_team, on="player_id", how="left")
    bowling_stats = bowling_stats.merge(current_team, on="player_id", how="left")

    outputs = {
        "batting_stats.csv": batting_stats,
        "bowling_stats.csv": bowling_stats,
        "team_stats.csv": team_stats,
        "venue_stats.csv": venue_stats,
        "head_to_head.csv": head_to_head,
        "season_trends.csv": season_trends,
        "phase_trends.csv": phase_trends,
        "dismissal_breakdown.csv": dismissal_breakdown,
        "matches_bi.csv": matches_bi,
        "overview_kpis.csv": overview_kpis,
        "batting_percentiles.csv": batting_percentiles,
    }
    for filename, df in outputs.items():
        df.to_csv(PROCESSED_DIR / filename, index=False)
        print(f"{filename:<20} {len(df):>6} rows -> {PROCESSED_DIR / filename}")


if __name__ == "__main__":
    main()
