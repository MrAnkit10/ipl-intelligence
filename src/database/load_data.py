"""Load the processed Parquet/CSV tables into PostgreSQL (blueprint section 31).

Requires PostgreSQL running and sql/schema.sql already applied:
    psql -d ipl_intelligence -f sql/schema.sql

Loads in dependency order: dim_player, dim_team, dim_venue, then the fact
tables. Team names in the fact tables are the canonical, normalized names
(src/data/team_normalization.py) so foreign keys to dim_team resolve
correctly; the original historical names are kept alongside on
fact_matches for auditability, never silently discarded.

Usage:
    python -m src.database.load_data
"""

from pathlib import Path

import pandas as pd

from src.data.team_normalization import TEAM_MAPPING, canonical_team_name, team_code
from src.data.venue_normalization import canonical_venue_name
from src.database.db import get_engine

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def load_dim_player(engine) -> None:
    players = pd.read_parquet(PROCESSED_DIR / "players.parquet")
    dim_player = players[["player_id", "display_name", "register_name", "unique_name", "key_cricinfo"]].copy()
    dim_player["photo_url"] = None
    dim_player.to_sql("dim_player", engine, if_exists="append", index=False, method="multi", chunksize=2000)
    print(f"dim_player:  {len(dim_player):,} rows")


def load_dim_team(engine, matches: pd.DataFrame) -> None:
    raw_names = pd.unique(matches[["team1", "team2"]].values.ravel())
    canonical_names = sorted({canonical_team_name(n) for n in raw_names})

    reverse_map = {}
    for original, canonical in TEAM_MAPPING.items():
        reverse_map.setdefault(canonical, set()).add(original)

    rows = []
    for name in canonical_names:
        originals = reverse_map.get(name, set()) | {name}
        rows.append({"team_name": name, "team_code": team_code(name), "original_names": sorted(originals)})

    dim_team = pd.DataFrame(rows)
    dim_team.to_sql("dim_team", engine, if_exists="append", index=False, method="multi", chunksize=500)
    print(f"dim_team:    {len(dim_team):,} rows")


def load_dim_venue(engine, matches: pd.DataFrame) -> None:
    matches = matches.copy()
    matches["venue"] = matches["venue"].map(canonical_venue_name, na_action="ignore")
    dim_venue = (
        matches.groupby("venue")["city"].agg(lambda s: s.mode().iat[0] if not s.mode().empty else None).reset_index()
    )
    dim_venue = dim_venue.rename(columns={"venue": "canonical_name"})
    dim_venue["country"] = None  # not captured in Cricsheet; IPL has been played outside India (2009 ZAF, 2014/2020 UAE)
    dim_venue.to_sql("dim_venue", engine, if_exists="append", index=False, method="multi", chunksize=500)
    print(f"dim_venue:   {len(dim_venue):,} rows")


def load_fact_matches(engine) -> None:
    matches_bi = pd.read_csv(PROCESSED_DIR / "matches_bi.csv", parse_dates=["date"])
    fact_matches = matches_bi.rename(columns={"team1": "team1_original", "team2": "team2_original"})
    # Overwrite (not rename, to avoid colliding with the original columns
    # of the same name) toss_winner/winner with their canonical values.
    fact_matches["team1"] = fact_matches["canonical_team1"]
    fact_matches["team2"] = fact_matches["canonical_team2"]
    fact_matches["toss_winner"] = fact_matches["canonical_toss_winner"]
    fact_matches["winner"] = fact_matches["canonical_winner"]
    fact_matches["venue_original"] = fact_matches["venue"]
    fact_matches["venue"] = fact_matches["canonical_venue"]
    columns = [
        "match_id", "season", "season_year", "date", "event_name", "match_number",
        "team1", "team2", "team1_original", "team2_original", "venue", "venue_original", "city",
        "toss_winner", "toss_decision", "winner", "outcome_type", "result_type",
        "win_by_runs", "win_by_wickets", "method", "player_of_match",
    ]
    fact_matches = fact_matches[columns]
    fact_matches.to_sql("fact_matches", engine, if_exists="append", index=False, method="multi", chunksize=1000)
    print(f"fact_matches: {len(fact_matches):,} rows")


def load_fact_deliveries(engine) -> None:
    deliveries = pd.read_parquet(PROCESSED_DIR / "deliveries.parquet")
    fact_deliveries = deliveries.copy()
    for col in ["batting_team", "bowling_team"]:
        fact_deliveries[col] = fact_deliveries[col].map(canonical_team_name, na_action="ignore")
    fact_deliveries["venue"] = fact_deliveries["venue"].map(canonical_venue_name, na_action="ignore")

    columns = [
        "delivery_id", "match_id", "season_year", "date", "venue", "innings", "is_super_over",
        "over", "ball", "phase", "batting_team", "bowling_team",
        "batter_id", "bowler_id", "non_striker_id", "runs_batter", "runs_extras", "runs_total",
        "extra_wides", "extra_noballs", "extra_byes", "extra_legbyes", "extra_penalty",
        "is_wicket", "player_dismissed_id", "dismissal_kind",
    ]
    fact_deliveries = fact_deliveries[columns]
    fact_deliveries.to_sql(
        "fact_deliveries", engine, if_exists="append", index=False, method="multi", chunksize=5000
    )
    print(f"fact_deliveries: {len(fact_deliveries):,} rows")


def load_fact_batting(engine) -> None:
    batting_stats = pd.read_csv(PROCESSED_DIR / "batting_stats.csv")
    columns = [
        "player_id", "innings", "runs", "balls_faced", "batting_average", "strike_rate",
        "fours", "sixes", "fifties", "hundreds", "boundary_pct", "dot_ball_pct",
    ]
    fact_batting = batting_stats[columns]
    fact_batting.to_sql("fact_batting", engine, if_exists="append", index=False, method="multi", chunksize=1000)
    print(f"fact_batting: {len(fact_batting):,} rows")


def load_fact_bowling(engine) -> None:
    bowling_stats = pd.read_csv(PROCESSED_DIR / "bowling_stats.csv")
    columns = [
        "player_id", "balls_bowled", "overs", "runs_conceded", "wickets", "economy",
        "bowling_average", "bowling_strike_rate", "dot_ball_pct", "boundary_conceded_pct",
    ]
    fact_bowling = bowling_stats[columns]
    fact_bowling.to_sql("fact_bowling", engine, if_exists="append", index=False, method="multi", chunksize=1000)
    print(f"fact_bowling: {len(fact_bowling):,} rows")


def main() -> None:
    engine = get_engine()
    matches = pd.read_parquet(PROCESSED_DIR / "matches.parquet")

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "TRUNCATE fact_predictions, fact_deliveries, fact_matches, fact_batting, fact_bowling, "
            "dim_player, dim_team, dim_venue RESTART IDENTITY CASCADE"
        )

    load_dim_player(engine)
    load_dim_team(engine, matches)
    load_dim_venue(engine, matches)
    load_fact_matches(engine)
    load_fact_deliveries(engine)
    load_fact_batting(engine)
    load_fact_bowling(engine)
    print("\nLoad complete.")


if __name__ == "__main__":
    main()
