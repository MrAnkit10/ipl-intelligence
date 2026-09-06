"""Season-level awards: champion, Orange Cap (most runs), Purple Cap (most
wickets), and the final's Player of the Match — everything Cricsheet
actually records. There is no tournament-wide MVP/"Player of the Series"
field in Cricsheet, only player_of_match per individual game, so that is
the one award this project doesn't attempt to reproduce.
"""

from __future__ import annotations

import pandas as pd

from src.analytics.bowling import BOWLER_CREDITED_DISMISSALS


def compute_season_awards(matches: pd.DataFrame, deliveries: pd.DataFrame) -> pd.DataFrame:
    main = deliveries[~deliveries["is_super_over"]]
    faced = main[main["extra_wides"] == 0]

    season_runs = (
        faced.groupby(["season_year", "batter_id", "batter"])["runs_batter"]
        .sum()
        .reset_index(name="runs")
    )
    orange_cap = season_runs.loc[season_runs.groupby("season_year")["runs"].idxmax()].set_index("season_year")

    bowler_wickets = main[main["dismissal_kind"].isin(BOWLER_CREDITED_DISMISSALS)]
    season_wickets = (
        bowler_wickets.groupby(["season_year", "bowler_id", "bowler"])
        .size()
        .reset_index(name="wickets")
    )
    purple_cap = season_wickets.loc[season_wickets.groupby("season_year")["wickets"].idxmax()].set_index(
        "season_year"
    )

    rows = []
    for season_year, season_matches in matches.groupby("season_year"):
        season_matches = season_matches.sort_values("date")
        final_match = season_matches.iloc[-1]
        champion = final_match["winner"] if final_match["outcome_type"] == "win" else None

        oc = orange_cap.loc[season_year] if season_year in orange_cap.index else None
        pc = purple_cap.loc[season_year] if season_year in purple_cap.index else None

        rows.append(
            {
                "season_year": season_year,
                "season_label": season_matches["season"].iloc[0],
                "champion": champion,
                "orange_cap_player_id": oc["batter_id"] if oc is not None else None,
                "orange_cap_name": oc["batter"] if oc is not None else None,
                "orange_cap_runs": int(oc["runs"]) if oc is not None else None,
                "purple_cap_player_id": pc["bowler_id"] if pc is not None else None,
                "purple_cap_name": pc["bowler"] if pc is not None else None,
                "purple_cap_wickets": int(pc["wickets"]) if pc is not None else None,
                "final_match_id": int(final_match["match_id"]),
                "final_potm_player_id": None,
                "final_potm_name": final_match["player_of_match"],
            }
        )

    awards = pd.DataFrame(rows)

    name_to_id = dict(zip(main["batter"], main["batter_id"]))
    name_to_id.update(dict(zip(main["bowler"], main["bowler_id"])))
    awards["final_potm_player_id"] = awards["final_potm_name"].map(name_to_id)

    return awards.sort_values("season_year", ascending=False).reset_index(drop=True)
