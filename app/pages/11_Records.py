import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from app.components import chart_card, inject_theme_css, render_html, render_page_title
from app.data_loader import (
    load_records_batting_extremes,
    load_records_biggest_wins,
    load_records_partnerships,
    load_records_team_totals,
    team_color,
)

st.set_page_config(page_title="Records & Milestones | IPL Intelligence", page_icon="🏅", layout="wide")
inject_theme_css()
render_page_title(
    "Records & Milestones",
    "The extremes of 19 seasons — biggest wins, highest and lowest totals, best partnerships, "
    "and the fastest fifties and hundreds — all derived directly from ball-by-ball data.",
    "#B45309",
)

def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _hero_card(eyebrow: str, title: str, subtitle: str, color: str) -> None:
    render_html(
        f"""
        <div style="border-radius:14px;overflow:hidden;margin-bottom:16px;
                    background:linear-gradient(90deg,{color}CC 0%,#0A0E27 100%);
                    border:1px solid {color}88;padding:16px 20px;">
            <div style="color:#DDE3FF;font-size:11px;font-weight:700;letter-spacing:0.06em;
                        text-transform:uppercase;">{eyebrow}</div>
            <div style="color:white;font-size:20px;font-weight:900;font-family:sans-serif;margin-top:2px;">{title}</div>
            <div style="color:#B8C0E0;font-size:13px;font-family:sans-serif;margin-top:2px;">{subtitle}</div>
        </div>
        """
    )


# --- Biggest Wins ---------------------------------------------------------
wins = load_records_biggest_wins()
if not wins.empty:
    top_win = wins[wins["margin_type"] == "runs"].iloc[0]
    _hero_card(
        "Biggest Win — By Runs",
        f"{top_win['winner']} won by {int(top_win['margin_value'])} runs",
        f"{top_win['team1']} vs {top_win['team2']} · {top_win['venue']} · {pd.to_datetime(top_win['date']).strftime('%d %b %Y')}",
        "#EF4444",
    )

win_col1, win_col2 = st.columns(2)
with win_col1:
    with chart_card("Biggest Wins — By Runs", "Largest winning margins in the tournament's history"):
        by_runs = wins[wins["margin_type"] == "runs"].copy()
        by_runs["date"] = pd.to_datetime(by_runs["date"]).dt.strftime("%Y-%m-%d")
        by_runs["Margin"] = by_runs["margin_value"].astype(int).astype(str) + " runs"
        st.dataframe(
            by_runs[["date", "team1", "team2", "winner", "Margin", "venue"]].rename(
                columns={"date": "Date", "team1": "Team 1", "team2": "Team 2", "winner": "Winner", "venue": "Venue"}
            ),
            width="stretch", hide_index=True, height=380,
        )
with win_col2:
    with chart_card("Biggest Wins — By Wickets", "Most one-sided chases, ranked by wickets in hand"):
        by_wkts = wins[wins["margin_type"] == "wickets"].copy()
        by_wkts["date"] = pd.to_datetime(by_wkts["date"]).dt.strftime("%Y-%m-%d")
        by_wkts["Margin"] = by_wkts["margin_value"].astype(int).astype(str) + " wkts"
        st.dataframe(
            by_wkts[["date", "team1", "team2", "winner", "Margin", "venue"]].rename(
                columns={"date": "Date", "team1": "Team 1", "team2": "Team 2", "winner": "Winner", "venue": "Venue"}
            ),
            width="stretch", hide_index=True, height=380,
        )

st.divider()

# --- Team Totals -----------------------------------------------------------
totals = load_records_team_totals()
tot_col1, tot_col2 = st.columns(2)
with tot_col1:
    with chart_card("Highest Team Totals", "Biggest single-innings scores"):
        highest = totals[totals["category"] == "highest"].copy()
        highest["date"] = pd.to_datetime(highest["date"]).dt.strftime("%Y-%m-%d")
        highest["Score"] = highest["total_runs"].astype(str) + "/" + highest["wickets"].astype(str)
        st.dataframe(
            highest[["date", "batting_team", "bowling_team", "Score", "venue"]].rename(
                columns={"date": "Date", "batting_team": "Team", "bowling_team": "Opponent", "venue": "Venue"}
            ),
            width="stretch", hide_index=True, height=380,
        )
with tot_col2:
    with chart_card("Lowest Team Totals", "Lowest completed (all-out) innings"):
        lowest = totals[totals["category"] == "lowest"].copy()
        lowest["date"] = pd.to_datetime(lowest["date"]).dt.strftime("%Y-%m-%d")
        lowest["Score"] = lowest["total_runs"].astype(str) + "/" + lowest["wickets"].astype(str)
        st.dataframe(
            lowest[["date", "batting_team", "bowling_team", "Score", "venue"]].rename(
                columns={"date": "Date", "batting_team": "Team", "bowling_team": "Opponent", "venue": "Venue"}
            ),
            width="stretch", hide_index=True, height=380,
        )

st.divider()

# --- Partnerships ------------------------------------------------------------
partnerships = load_records_partnerships()
if not partnerships.empty:
    top_p = partnerships.iloc[0]
    with chart_card("Best Partnerships", "Highest partnership for any wicket, by runs added"):
        color = team_color(top_p["batting_team"])
        render_html(
            f"""
            <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;
                        background:linear-gradient(90deg,{color}55 0%,#131A3A 70%);border:1px solid {color}88;
                        border-radius:12px;padding:14px 18px;">
                <div style="color:white;font-family:sans-serif;flex:1;">
                    <div style="font-size:22px;font-weight:900;">{int(top_p['runs'])} runs</div>
                    <div style="font-size:14px;color:#DDE3FF;">{top_p['batter1']} &amp; {top_p['batter2']}
                        · {_ordinal(int(top_p['wicket_number']))} wicket · {top_p['batting_team']}</div>
                    <div style="font-size:12px;color:#8892C0;margin-top:2px;">
                        {top_p['venue']} · {pd.to_datetime(top_p['date']).strftime('%d %b %Y')} · off {int(top_p['balls'])} balls
                    </div>
                </div>
            </div>
            """
        )
        table = partnerships.copy()
        table["date"] = pd.to_datetime(table["date"]).dt.strftime("%Y-%m-%d")
        table["Wicket"] = table["wicket_number"].apply(_ordinal)
        table["Pair"] = table["batter1"] + " & " + table["batter2"]
        st.dataframe(
            table[["date", "Pair", "Wicket", "runs", "balls", "batting_team", "venue"]].rename(
                columns={"date": "Date", "runs": "Runs", "balls": "Balls", "batting_team": "Team", "venue": "Venue"}
            ),
            width="stretch", hide_index=True, height=380,
        )

st.divider()

# --- Batting Extremes --------------------------------------------------------
extremes = load_records_batting_extremes()
ext_col1, ext_col2 = st.columns(2)
with ext_col1:
    with chart_card("Fastest Fifties", "Fewest balls to reach 50 runs"):
        fifty = extremes[extremes["category"] == "fastest_fifty"].copy()
        fifty["date"] = pd.to_datetime(fifty["date"]).dt.strftime("%Y-%m-%d")
        st.dataframe(
            fifty[["date", "batter", "runs", "balls_to_milestone", "bowling_team", "venue"]].rename(
                columns={"date": "Date", "batter": "Batter", "runs": "Runs",
                         "balls_to_milestone": "Balls to 50", "bowling_team": "Vs", "venue": "Venue"}
            ),
            width="stretch", hide_index=True, height=340,
        )
    with chart_card("Most Sixes in an Innings", ""):
        sixes = extremes[extremes["category"] == "most_sixes"].copy()
        sixes["date"] = pd.to_datetime(sixes["date"]).dt.strftime("%Y-%m-%d")
        st.dataframe(
            sixes[["date", "batter", "runs", "sixes", "bowling_team"]].rename(
                columns={"date": "Date", "batter": "Batter", "runs": "Runs", "sixes": "6s", "bowling_team": "Vs"}
            ),
            width="stretch", hide_index=True, height=280,
        )
with ext_col2:
    with chart_card("Fastest Hundreds", "Fewest balls to reach 100 runs"):
        hundred = extremes[extremes["category"] == "fastest_hundred"].copy()
        hundred["date"] = pd.to_datetime(hundred["date"]).dt.strftime("%Y-%m-%d")
        st.dataframe(
            hundred[["date", "batter", "runs", "balls_to_milestone", "bowling_team", "venue"]].rename(
                columns={"date": "Date", "batter": "Batter", "runs": "Runs",
                         "balls_to_milestone": "Balls to 100", "bowling_team": "Vs", "venue": "Venue"}
            ),
            width="stretch", hide_index=True, height=340,
        )
    with chart_card("Most Fours in an Innings", ""):
        fours = extremes[extremes["category"] == "most_fours"].copy()
        fours["date"] = pd.to_datetime(fours["date"]).dt.strftime("%Y-%m-%d")
        st.dataframe(
            fours[["date", "batter", "runs", "fours", "bowling_team"]].rename(
                columns={"date": "Date", "batter": "Batter", "runs": "Runs", "fours": "4s", "bowling_team": "Vs"}
            ),
            width="stretch", hide_index=True, height=280,
        )
