"""Small reusable UI pieces shared across pages."""

import hashlib

import streamlit as st

from src.data.team_normalization import team_code

AVATAR_COLORS = [
    "#EC1C24", "#004BA0", "#FDB913", "#3A225D", "#EA1A85",
    "#17479E", "#FF822A", "#1B2133", "#A72056", "#0D3692",
]


def inject_theme_css() -> None:
    """Site-wide visual polish: card-style metrics, rounded bordered
    containers, tighter spacing — call once near the top of every page,
    right after st.set_page_config()."""
    st.markdown(
        """
        <style>
        [data-testid="stMetric"] {
            background: linear-gradient(180deg, #131A3A 0%, #0F1530 100%);
            border: 1px solid #232B55;
            border-radius: 12px;
            padding: 14px 16px 10px 16px;
        }
        [data-testid="stMetricLabel"] { opacity: 0.75; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px !important;
        }
        h1, h2, h3 { letter-spacing: -0.01em; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_team_badge(team: str, color: str, size: int = 64) -> None:
    """A colored rounded-square badge with the team's short code — used
    instead of official team crests, which are trademarked and not safe
    to hotlink on a public deployment."""
    code = team_code(team)
    font_size = max(size // 3, 12)
    st.markdown(
        f"""
        <div style="width:{size}px;height:{size}px;border-radius:{size // 5}px;
                    background:linear-gradient(135deg,{color} 0%,{color}CC 100%);
                    color:white;display:flex;align-items:center;justify-content:center;
                    font-size:{font_size}px;font-weight:800;font-family:sans-serif;
                    box-shadow:0 4px 12px {color}55;">
            {code}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_match_banner(
    team1: str, team1_color: str, team1_score: str,
    team2: str, team2_color: str, team2_score: str,
    subtitle: str,
) -> None:
    """A full-width gradient scorecard header, split between the two teams'
    colors — mirrors a broadcast match-center header without using any
    trademarked logo imagery (team badges are the colored code chips from
    render_team_badge, rendered inline as text)."""
    team1_code, team2_code = team_code(team1), team_code(team2)
    st.markdown(
        f"""
        <div style="border-radius:16px;overflow:hidden;margin-bottom:6px;">
            <div style="display:flex;background:linear-gradient(90deg,{team1_color} 0%,{team1_color}CC 48%,
                        #0A0E27 50%,{team2_color}CC 52%,{team2_color} 100%);padding:22px 28px;">
                <div style="flex:1;color:white;font-family:sans-serif;">
                    <div style="font-size:13px;opacity:0.85;font-weight:600;">{team1_code}</div>
                    <div style="font-size:20px;font-weight:800;">{team1}</div>
                    <div style="font-size:26px;font-weight:800;margin-top:4px;">{team1_score}</div>
                </div>
                <div style="align-self:center;color:white;opacity:0.7;font-weight:700;
                            font-family:sans-serif;padding:0 16px;">VS</div>
                <div style="flex:1;color:white;font-family:sans-serif;text-align:right;">
                    <div style="font-size:13px;opacity:0.85;font-weight:600;">{team2_code}</div>
                    <div style="font-size:20px;font-weight:800;">{team2}</div>
                    <div style="font-size:26px;font-weight:800;margin-top:4px;">{team2_score}</div>
                </div>
            </div>
            <div style="background:#131A3A;color:#B8C0E0;text-align:center;padding:8px;
                        font-size:13px;font-family:sans-serif;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _initials(name: str) -> str:
    parts = [p for p in name.replace(".", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _color_for(name: str) -> str:
    digest = hashlib.md5(name.encode()).hexdigest()
    return AVATAR_COLORS[int(digest, 16) % len(AVATAR_COLORS)]


def render_avatar(name: str, photo_url: str | None, size: int = 120) -> None:
    """Shows a real photo if one was found, otherwise a colored initials
    avatar — never a broken image or a wrong photo."""
    if photo_url:
        st.image(photo_url, width=size)
    else:
        initials = _initials(name)
        color = _color_for(name)
        st.markdown(
            f"""
            <div style="width:{size}px;height:{size}px;border-radius:50%;
                        background:{color};color:white;display:flex;
                        align-items:center;justify-content:center;
                        font-size:{size // 3}px;font-weight:700;
                        font-family:sans-serif;">
                {initials}
            </div>
            """,
            unsafe_allow_html=True,
        )
