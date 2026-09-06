"""Team-level and venue-level analytics (blueprint sections 2 and 8)."""

from itertools import combinations

import numpy as np
import pandas as pd

from src.data.team_normalization import canonical_team_name
from src.data.venue_normalization import canonical_venue_name


def _with_canonical_team_names(matches: pd.DataFrame) -> pd.DataFrame:
    """Apply team-name normalization (blueprint section 42) without mutating
    the caller's frame or the underlying matches.parquet."""
    matches = matches.copy()
    for col in ["team1", "team2", "toss_winner", "winner"]:
        matches[col] = matches[col].map(canonical_team_name, na_action="ignore")
    return matches


def compute_team_stats(matches: pd.DataFrame) -> pd.DataFrame:
    """One row per team: matches played, win %, toss impact, chase vs defend record."""
    matches = _with_canonical_team_names(matches)
    teams = pd.unique(matches[["team1", "team2"]].values.ravel())
    rows = []
    decided = matches[matches["outcome_type"] == "win"]

    for team in sorted(teams):
        played = matches[(matches["team1"] == team) | (matches["team2"] == team)]
        team_decided = decided[(decided["team1"] == team) | (decided["team2"] == team)]
        wins = (team_decided["winner"] == team).sum()

        toss_won = played[played["toss_winner"] == team]
        toss_won_and_match_won = (toss_won["winner"] == team).sum()

        # Batting-first vs chasing: team batted first if it won the toss and chose
        # to bat, or lost the toss and the opponent chose to field.
        bat_first_mask = (
            ((played["toss_winner"] == team) & (played["toss_decision"] == "bat"))
            | ((played["toss_winner"] != team) & (played["toss_decision"] == "field"))
        )
        batted_first = played[bat_first_mask]
        chased = played[~bat_first_mask]
        batted_first_decided = batted_first[batted_first["outcome_type"] == "win"]
        chased_decided = chased[chased["outcome_type"] == "win"]

        rows.append(
            {
                "team": team,
                "matches_played": len(played),
                "wins": int(wins),
                "losses": int(len(team_decided) - wins),
                "no_results": int(len(played) - len(team_decided)),
                "win_pct": round(wins / len(team_decided) * 100, 2) if len(team_decided) else np.nan,
                "toss_won": len(toss_won),
                "toss_won_and_match_won_pct": (
                    round(toss_won_and_match_won / len(toss_won) * 100, 2) if len(toss_won) else np.nan
                ),
                "matches_batted_first": len(batted_first),
                "win_pct_batting_first": (
                    round((batted_first_decided["winner"] == team).sum() / len(batted_first_decided) * 100, 2)
                    if len(batted_first_decided)
                    else np.nan
                ),
                "matches_chased": len(chased),
                "win_pct_chasing": (
                    round((chased_decided["winner"] == team).sum() / len(chased_decided) * 100, 2)
                    if len(chased_decided)
                    else np.nan
                ),
            }
        )

    return pd.DataFrame(rows).sort_values("wins", ascending=False).reset_index(drop=True)


def compute_venue_stats(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    """One row per venue (blueprint section 8)."""
    matches = _with_canonical_team_names(matches)
    matches["venue"] = matches["venue"].map(canonical_venue_name, na_action="ignore")
    main = deliveries[~deliveries["is_super_over"]].copy()
    main["venue"] = main["venue"].map(canonical_venue_name, na_action="ignore")

    innings_totals = (
        main.groupby(["match_id", "innings"])
        .agg(venue=("venue", "first"), runs=("runs_total", "sum"))
        .reset_index()
    )
    first_innings = innings_totals[innings_totals["innings"] == 1]

    powerplay = main[main["phase"] == "powerplay"].groupby(["match_id", "innings"])["runs_total"].sum()
    death = main[main["phase"] == "death"].groupby(["match_id", "innings"])["runs_total"].sum()
    innings_totals = innings_totals.set_index(["match_id", "innings"])
    innings_totals["powerplay_runs"] = powerplay
    innings_totals["death_runs"] = death
    innings_totals = innings_totals.reset_index()

    decided = matches[matches["outcome_type"] == "win"]
    bat_first_mask = (
        ((decided["toss_winner"] == decided["winner"]) & (decided["toss_decision"] == "bat"))
        | ((decided["toss_winner"] != decided["winner"]) & (decided["toss_decision"] == "field"))
    )
    defending_wins = bat_first_mask.groupby(decided["venue"]).sum()
    decided_counts = decided.groupby("venue").size()

    rows = []
    for venue, played in matches.groupby("venue"):
        venue_first_innings = first_innings[first_innings["venue"] == venue]
        venue_innings = innings_totals[innings_totals["venue"] == venue]
        n_decided = decided_counts.get(venue, 0)
        n_defending_wins = defending_wins.get(venue, 0)
        most_successful = (
            played.loc[played["outcome_type"] == "win", "winner"].value_counts().idxmax()
            if (played["outcome_type"] == "win").any()
            else None
        )

        rows.append(
            {
                "venue": venue,
                "city": played["city"].mode().iat[0] if not played["city"].mode().empty else None,
                "matches_played": len(played),
                "avg_first_innings_score": round(venue_first_innings["runs"].mean(), 1)
                if len(venue_first_innings)
                else np.nan,
                "avg_powerplay_score": round(venue_innings["powerplay_runs"].mean(), 1)
                if venue_innings["powerplay_runs"].notna().any()
                else np.nan,
                "avg_death_overs_score": round(venue_innings["death_runs"].mean(), 1)
                if venue_innings["death_runs"].notna().any()
                else np.nan,
                "defending_win_pct": round(n_defending_wins / n_decided * 100, 2) if n_decided else np.nan,
                "chasing_win_pct": round((1 - n_defending_wins / n_decided) * 100, 2) if n_decided else np.nan,
                "most_successful_team": most_successful,
            }
        )

    return pd.DataFrame(rows).sort_values("matches_played", ascending=False).reset_index(drop=True)


def compute_head_to_head(matches: pd.DataFrame) -> pd.DataFrame:
    """One row per unordered team pair with an IPL meeting: matches played
    and each side's win count (blueprint sections 25, 37)."""
    matches = _with_canonical_team_names(matches)
    decided = matches[matches["outcome_type"] == "win"]
    teams = sorted(pd.unique(matches[["team1", "team2"]].values.ravel()))

    rows = []
    for team_a, team_b in combinations(teams, 2):
        pair_mask = ((decided["team1"] == team_a) & (decided["team2"] == team_b)) | (
            (decided["team1"] == team_b) & (decided["team2"] == team_a)
        )
        pair_matches = decided[pair_mask]
        if pair_matches.empty:
            continue
        team_a_wins = int((pair_matches["winner"] == team_a).sum())
        team_b_wins = int((pair_matches["winner"] == team_b).sum())
        rows.append(
            {
                "team_a": team_a,
                "team_b": team_b,
                "matches_played": len(pair_matches),
                "team_a_wins": team_a_wins,
                "team_b_wins": team_b_wins,
                "team_a_win_pct": round(team_a_wins / len(pair_matches) * 100, 2),
            }
        )

    return pd.DataFrame(rows).sort_values("matches_played", ascending=False).reset_index(drop=True)


def compute_season_trends(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    """One row per season: scoring and results trends over time (blueprint
    section 37, "season trends")."""
    matches = _with_canonical_team_names(matches)
    main = deliveries[~deliveries["is_super_over"]]

    innings_totals = main.groupby(["match_id", "innings", "season_year"])["runs_total"].sum().reset_index()

    # Winner batted first if it won the toss and chose to bat, or lost the
    # toss and the opponent chose to field (same pattern as compute_venue_stats).
    decided = matches[matches["outcome_type"] == "win"]
    winner_batted_first = ((decided["toss_winner"] == decided["winner"]) & (decided["toss_decision"] == "bat")) | (
        (decided["toss_winner"] != decided["winner"]) & (decided["toss_decision"] == "field")
    )
    chasing_win_by_season = (~winner_batted_first).groupby(decided["season_year"]).mean() * 100

    rows = []
    for season, season_matches in matches.groupby("season_year"):
        season_innings = innings_totals[innings_totals["season_year"] == season]
        season_deliveries = main[main["season_year"] == season]
        rows.append(
            {
                "season_year": season,
                "matches_played": len(season_matches),
                "avg_innings_score": round(season_innings["runs_total"].mean(), 1) if len(season_innings) else np.nan,
                "total_sixes": int((season_deliveries["runs_batter"] == 6).sum()),
                "total_fours": int((season_deliveries["runs_batter"] == 4).sum()),
                "total_wickets": int(season_deliveries["is_wicket"].sum()),
                "chasing_wins_pct": round(chasing_win_by_season.get(season, np.nan), 2),
            }
        )

    return pd.DataFrame(rows).sort_values("season_year").reset_index(drop=True)
