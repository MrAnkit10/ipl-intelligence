"""Parse raw Cricsheet IPL JSON files into clean, flat analytical tables.

Produces (under data/processed/):
    matches.parquet / matches.csv
    deliveries.parquet / deliveries.csv
    players.parquet / players.csv

Design notes
------------
- Every Cricsheet IPL file seen so far is data_version 1.2.0. If a future
  download includes an older schema this parser will raise, rather than
  silently misparse it.
- Player identity uses the stable id from each match's info.registry.people
  mapping (backed by Cricsheet's global people register), never the display
  name alone, per the identity-management approach in the project blueprint.
- "ball" on a delivery is the legal-ball count within the over (1-6);
  extras (wides/no-balls) do not increment it, matching the on-field
  convention that an extra is bowled "again" as the same ball number.
- "phase" (powerplay/middle/death, blueprint section 27) is keyed off the
  absolute over index; super overs get their own phase since over indices
  there restart at 0 and don't mean "powerplay".
- Raw files are never modified; this script only reads data/raw and writes
  data/processed.

Usage:
    python -m src.data.parse_cricsheet
"""

import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_CRICSHEET_DIR = BASE_DIR / "data" / "raw" / "cricsheet" / "ipl_json"
PEOPLE_CSV = BASE_DIR / "data" / "raw" / "player_metadata" / "people.csv"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

SUPPORTED_DATA_VERSION = "1.2.0"


def _extract_season_year(season_value) -> int:
    """Cricsheet stores season as e.g. 2020 or '2007/08'; normalize to a year."""
    text = str(season_value)
    return int(text[:4])


def _phase(over_number: int, is_super_over: bool) -> str:
    if is_super_over:
        return "super_over"
    if over_number < 6:
        return "powerplay"
    if over_number < 15:
        return "middle"
    return "death"


def _parse_outcome(outcome: dict) -> dict:
    if "winner" in outcome:
        by = outcome.get("by", {})
        return {
            "winner": outcome["winner"],
            "outcome_type": "win",
            "result_type": "runs" if "runs" in by else ("wickets" if "wickets" in by else "other"),
            "win_by_runs": by.get("runs"),
            "win_by_wickets": by.get("wickets"),
            "method": outcome.get("method"),
        }
    if "eliminator" in outcome:
        return {
            "winner": outcome["eliminator"],
            "outcome_type": "tie_super_over",
            "result_type": "super_over",
            "win_by_runs": None,
            "win_by_wickets": None,
            "method": outcome.get("method"),
        }
    # {'result': 'no result'} or an unresolved tie with no eliminator on record
    return {
        "winner": None,
        "outcome_type": outcome.get("result", "unknown").replace(" ", "_"),
        "result_type": outcome.get("result", "unknown").replace(" ", "_"),
        "win_by_runs": None,
        "win_by_wickets": None,
        "method": outcome.get("method"),
    }


def parse_match_file(json_path: Path) -> tuple[dict, list[dict]]:
    with open(json_path) as f:
        data = json.load(f)

    data_version = data["meta"]["data_version"]
    if data_version != SUPPORTED_DATA_VERSION:
        raise ValueError(
            f"{json_path.name}: unsupported Cricsheet data_version {data_version} "
            f"(parser targets {SUPPORTED_DATA_VERSION})"
        )

    info = data["info"]
    match_id = int(json_path.stem)
    registry = info.get("registry", {}).get("people", {})

    team1, team2 = info["teams"][0], info["teams"][1]
    outcome_fields = _parse_outcome(info.get("outcome", {}))

    match_row = {
        "match_id": match_id,
        "season": str(info.get("season")),
        "season_year": _extract_season_year(info.get("season")),
        "date": info["dates"][0],
        "event_name": info.get("event", {}).get("name"),
        "match_number": info.get("event", {}).get("match_number"),
        "team1": team1,
        "team2": team2,
        "venue": info.get("venue"),
        "city": info.get("city"),
        "toss_winner": info.get("toss", {}).get("winner"),
        "toss_decision": info.get("toss", {}).get("decision"),
        "player_of_match": ";".join(info.get("player_of_match", [])) or None,
        "gender": info.get("gender"),
        "match_type": info.get("match_type"),
        "overs_per_innings": info.get("overs"),
        **outcome_fields,
    }

    delivery_rows = []
    for innings_number, innings in enumerate(data["innings"], start=1):
        batting_team = innings["team"]
        bowling_team = team2 if batting_team == team1 else team1
        is_super_over = bool(innings.get("super_over", False))

        for over in innings["overs"]:
            over_number = over["over"]
            legal_ball_count = 0
            for delivery in over["deliveries"]:
                extras = delivery.get("extras", {})
                is_legal = "wides" not in extras and "noballs" not in extras
                if is_legal:
                    legal_ball_count += 1
                    ball_number = legal_ball_count
                else:
                    ball_number = legal_ball_count + 1

                wickets = delivery.get("wickets", [])
                wicket = wickets[0] if wickets else None

                delivery_rows.append(
                    {
                        "match_id": match_id,
                        "season_year": match_row["season_year"],
                        "date": match_row["date"],
                        "venue": match_row["venue"],
                        "innings": innings_number,
                        "is_super_over": is_super_over,
                        "over": over_number,
                        "ball": ball_number,
                        "phase": _phase(over_number, is_super_over),
                        "actual_delivery": delivery.get("actual_delivery"),
                        "batting_team": batting_team,
                        "bowling_team": bowling_team,
                        "batter": delivery["batter"],
                        "bowler": delivery["bowler"],
                        "non_striker": delivery["non_striker"],
                        "batter_id": registry.get(delivery["batter"]),
                        "bowler_id": registry.get(delivery["bowler"]),
                        "non_striker_id": registry.get(delivery["non_striker"]),
                        "runs_batter": delivery["runs"]["batter"],
                        "runs_extras": delivery["runs"]["extras"],
                        "runs_total": delivery["runs"]["total"],
                        "extra_wides": extras.get("wides", 0),
                        "extra_noballs": extras.get("noballs", 0),
                        "extra_byes": extras.get("byes", 0),
                        "extra_legbyes": extras.get("legbyes", 0),
                        "extra_penalty": extras.get("penalty", 0),
                        "is_wicket": int(wicket is not None),
                        "player_dismissed": wicket["player_out"] if wicket else None,
                        "player_dismissed_id": registry.get(wicket["player_out"]) if wicket else None,
                        "dismissal_kind": wicket["kind"] if wicket else None,
                        "fielders": (
                            ";".join(f.get("name", "") for f in wicket.get("fielders", []))
                            if wicket
                            else None
                        ),
                    }
                )

    return match_row, delivery_rows


def build_players_table(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Build the player dimension from ids seen in the deliveries, enriched
    with canonical names / cross-platform keys from Cricsheet's people register."""
    id_name_pairs = pd.concat(
        [
            deliveries[["batter_id", "batter"]].rename(columns={"batter_id": "player_id", "batter": "player_name"}),
            deliveries[["bowler_id", "bowler"]].rename(columns={"bowler_id": "player_id", "bowler": "player_name"}),
        ]
    ).dropna(subset=["player_id"])

    # A player can appear under slightly different display-name spellings
    # across matches; keep the most frequently used one per id.
    name_counts = id_name_pairs.groupby(["player_id", "player_name"]).size().reset_index(name="n")
    most_common_name = (
        name_counts.sort_values("n", ascending=False).drop_duplicates(subset="player_id").drop(columns="n")
    )

    players = most_common_name.rename(columns={"player_name": "display_name"})

    if PEOPLE_CSV.exists():
        register = pd.read_csv(PEOPLE_CSV, dtype=str)
        register = register.rename(columns={"identifier": "player_id", "name": "register_name"})
        keep_cols = ["player_id", "register_name", "unique_name", "key_cricinfo"]
        register = register[[c for c in keep_cols if c in register.columns]]
        players = players.merge(register, on="player_id", how="left")

    return players.sort_values("display_name").reset_index(drop=True)


def build_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    json_files = sorted(RAW_CRICSHEET_DIR.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(
            f"No JSON files found in {RAW_CRICSHEET_DIR}. Run "
            "`python -m src.data.download_data` first."
        )

    match_rows = []
    all_delivery_rows = []
    for path in json_files:
        match_row, delivery_rows = parse_match_file(path)
        match_rows.append(match_row)
        all_delivery_rows.extend(delivery_rows)

    matches = pd.DataFrame(match_rows).sort_values("date").reset_index(drop=True)
    deliveries = pd.DataFrame(all_delivery_rows)
    deliveries.insert(0, "delivery_id", range(1, len(deliveries) + 1))

    matches["date"] = pd.to_datetime(matches["date"])
    deliveries["date"] = pd.to_datetime(deliveries["date"])

    players = build_players_table(deliveries)

    return matches, deliveries, players


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    matches, deliveries, players = build_tables()

    matches.to_parquet(PROCESSED_DIR / "matches.parquet", index=False)
    matches.to_csv(PROCESSED_DIR / "matches.csv", index=False)

    deliveries.to_parquet(PROCESSED_DIR / "deliveries.parquet", index=False)
    deliveries.to_csv(PROCESSED_DIR / "deliveries.csv", index=False)

    players.to_parquet(PROCESSED_DIR / "players.parquet", index=False)
    players.to_csv(PROCESSED_DIR / "players.csv", index=False)

    print(f"matches:    {len(matches):>7,} rows -> {PROCESSED_DIR / 'matches.parquet'}")
    print(f"deliveries: {len(deliveries):>7,} rows -> {PROCESSED_DIR / 'deliveries.parquet'}")
    print(f"players:    {len(players):>7,} rows -> {PROCESSED_DIR / 'players.parquet'}")


if __name__ == "__main__":
    main()
