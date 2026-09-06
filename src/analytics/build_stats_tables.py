"""Build the descriptive-analytics tables from matches/deliveries.

Writes to data/processed/: batting_stats.csv, bowling_stats.csv,
team_stats.csv, venue_stats.csv — matching the recommended raw/processed
data structure in the blueprint (section 10).

Usage:
    python -m src.analytics.build_stats_tables
"""

from pathlib import Path

import pandas as pd

from src.analytics.batting import compute_batting_stats
from src.analytics.bowling import compute_bowling_stats
from src.analytics.team_stats import compute_team_stats, compute_venue_stats

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def main() -> None:
    matches = pd.read_parquet(PROCESSED_DIR / "matches.parquet")
    deliveries = pd.read_parquet(PROCESSED_DIR / "deliveries.parquet")

    batting_stats = compute_batting_stats(deliveries)
    bowling_stats = compute_bowling_stats(deliveries)
    team_stats = compute_team_stats(matches)
    venue_stats = compute_venue_stats(matches, deliveries)

    batting_stats.to_csv(PROCESSED_DIR / "batting_stats.csv", index=False)
    bowling_stats.to_csv(PROCESSED_DIR / "bowling_stats.csv", index=False)
    team_stats.to_csv(PROCESSED_DIR / "team_stats.csv", index=False)
    venue_stats.to_csv(PROCESSED_DIR / "venue_stats.csv", index=False)

    print(f"batting_stats: {len(batting_stats):>4} players -> {PROCESSED_DIR / 'batting_stats.csv'}")
    print(f"bowling_stats: {len(bowling_stats):>4} players -> {PROCESSED_DIR / 'bowling_stats.csv'}")
    print(f"team_stats:    {len(team_stats):>4} teams   -> {PROCESSED_DIR / 'team_stats.csv'}")
    print(f"venue_stats:   {len(venue_stats):>4} venues  -> {PROCESSED_DIR / 'venue_stats.csv'}")


if __name__ == "__main__":
    main()
