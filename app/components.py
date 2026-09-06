"""Small reusable UI pieces shared across pages."""

import hashlib
from contextlib import contextmanager

import streamlit as st

from src.data.team_normalization import team_code

AVATAR_COLORS = [
    "#EC1C24", "#004BA0", "#FDB913", "#3A225D", "#EA1A85",
    "#17479E", "#FF822A", "#1B2133", "#A72056", "#0D3692",
]

# A small custom cricket-ball mark (plain SVG: a circle plus two seam
# curves) used in place of the 🏏 emoji and, deliberately, in place of
# any real IPL/BCCI branding — those are trademarked, and reproducing
# them (even redrawn) on a public deployment isn't something this
# project can safely do. This is an original, generic cricket icon.
BALL_ICON_SVG = """
<svg width="{size}" height="{size}" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="21" fill="{color}" stroke="#ffffff33" stroke-width="1.5"/>
    <path d="M 24 3 A 21 21 0 0 1 24 45" stroke="#ffffff88" stroke-width="1.2" fill="none" stroke-dasharray="2,2"/>
    <path d="M 8 12 A 21 21 0 0 0 8 36" stroke="#ffffff88" stroke-width="1.2" fill="none" stroke-dasharray="2,2"/>
</svg>
"""


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
            background: linear-gradient(180deg, #131A3A 0%, #0F1530 100%);
            border: 1px solid #232B55 !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] > div { padding: 4px 6px; }
        h1, h2, h3 { letter-spacing: -0.01em; }
        #MainMenu, footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_title(title: str, subtitle: str | None = None, color: str = "#3B82F6") -> None:
    """A designed page header (colored accent chip + bold title, optional
    subtitle) — replaces st.title("<emoji> Title"), which reads as a
    placeholder rather than a finished product."""
    ball = BALL_ICON_SVG.format(size=34, color=color)
    subtitle_html = f'<div style="color:#B8C0E0;font-size:13px;font-family:sans-serif;margin-top:2px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;">
            <div style="flex-shrink:0;">{ball}</div>
            <div>
                <div style="color:white;font-size:26px;font-weight:900;font-family:sans-serif;
                            letter-spacing:-0.02em;">{title}</div>
                {subtitle_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def chart_card(title: str, subtitle: str | None = None):
    """A bordered, dark-card section for a chart or table — the boxed-panel
    look of a broadcast stats page ("Manhattan", "Partnerships", ...),
    applied to this project's own charts."""
    with st.container(border=True):
        subtitle_html = (
            f'<div style="color:#8892C0;font-size:12px;font-family:sans-serif;margin-bottom:8px;">{subtitle}</div>'
            if subtitle else ""
        )
        st.markdown(
            f"""
            <div style="font-weight:800;font-size:15px;color:white;font-family:sans-serif;
                        margin:2px 0 2px 0;">{title}</div>
            {subtitle_html}
            """,
            unsafe_allow_html=True,
        )
        yield


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


def render_stat_card(
    name: str, subtitle: str, photo_url: str | None, color: str, rows: list[tuple[str, str]]
) -> None:
    """A dark broadcast-style stat card (name/subtitle banner, photo,
    labeled stat rows) — the visual language of the Bumrah-bowling-economy
    reference graphic, applied to stats this project actually has."""
    photo_html = (
        f'<img src="{photo_url}" style="width:100%;height:100%;object-fit:cover;" />'
        if photo_url
        else f'''<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;
                       background:{_color_for(name)};color:white;font-size:32px;font-weight:800;
                       font-family:sans-serif;">{_initials(name)}</div>'''
    )
    rows_html = "".join(
        f'''<div style="display:flex;justify-content:space-between;padding:8px 0;
                    border-bottom:1px solid #232B55;">
                <span style="color:#B8C0E0;font-size:13px;font-family:sans-serif;">{label}</span>
                <span style="color:white;font-weight:700;font-size:14px;font-family:sans-serif;">{value}</span>
            </div>'''
        for label, value in rows
    )
    st.markdown(
        f"""
        <div style="border-radius:14px;overflow:hidden;border:1px solid {color}88;
                    box-shadow:0 6px 16px rgba(0,0,0,0.35);margin-bottom:16px;">
            <div style="display:flex;background:linear-gradient(90deg,{color}CC 0%,#0A0E27 100%);">
                <div style="flex:1;padding:14px 16px;">
                    <div style="color:white;font-weight:900;font-size:18px;font-family:sans-serif;">{name}</div>
                    <div style="color:#DDE3FF;font-size:12px;font-family:sans-serif;">{subtitle}</div>
                </div>
                <div style="width:64px;height:64px;margin:8px;border-radius:10px;overflow:hidden;
                            flex-shrink:0;">{photo_html}</div>
            </div>
            <div style="background:#0F1530;padding:8px 16px;">{rows_html}</div>
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


def render_matchup_banner(
    player1: str, player1_color: str, player1_subtitle: str, player1_photo: str | None,
    player2: str, player2_color: str, player2_subtitle: str, player2_photo: str | None,
) -> None:
    """A split-gradient "vs" card for a head-to-head player matchup —
    same visual language as render_match_banner, with player photos
    instead of team codes and scores."""
    p1_photo_html = avatar_html(player1, player1_photo, size=72)
    p2_photo_html = avatar_html(player2, player2_photo, size=72)
    st.markdown(
        f"""
        <div style="border-radius:16px;overflow:hidden;margin-bottom:6px;
                    display:flex;align-items:center;
                    background:linear-gradient(90deg,{player1_color} 0%,{player1_color}CC 48%,
                    #0A0E27 50%,{player2_color}CC 52%,{player2_color} 100%);padding:20px 28px;">
            <div style="flex:1;display:flex;align-items:center;gap:14px;color:white;font-family:sans-serif;">
                {p1_photo_html}
                <div>
                    <div style="font-size:11px;opacity:0.85;font-weight:600;">{player1_subtitle}</div>
                    <div style="font-size:19px;font-weight:800;">{player1}</div>
                </div>
            </div>
            <div style="color:white;opacity:0.7;font-weight:700;font-family:sans-serif;padding:0 16px;">VS</div>
            <div style="flex:1;display:flex;align-items:center;justify-content:flex-end;gap:14px;
                        color:white;font-family:sans-serif;text-align:right;">
                <div>
                    <div style="font-size:11px;opacity:0.85;font-weight:600;">{player2_subtitle}</div>
                    <div style="font-size:19px;font-weight:800;">{player2}</div>
                </div>
                {p2_photo_html}
            </div>
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


def avatar_html(name: str, photo_url: str | None, size: int = 120) -> str:
    """Returns the avatar markup as a string (real photo if found, else a
    colored initials circle) so it can be embedded inside a larger custom
    HTML card in a single st.markdown call — splitting one card's HTML
    across multiple st.markdown/st.image calls doesn't actually nest in
    the DOM, since each call renders as its own sibling element."""
    if photo_url:
        return (
            f'<img src="{photo_url}" style="width:{size}px;height:{size}px;border-radius:50%;'
            f'object-fit:cover;" />'
        )
    initials = _initials(name)
    color = _color_for(name)
    return f"""
        <div style="width:{size}px;height:{size}px;border-radius:50%;
                    background:{color};color:white;display:flex;
                    align-items:center;justify-content:center;
                    font-size:{size // 3}px;font-weight:700;
                    font-family:sans-serif;">
            {initials}
        </div>
        """


def render_avatar(name: str, photo_url: str | None, size: int = 120) -> None:
    """Shows a real photo if one was found, otherwise a colored initials
    avatar — never a broken image or a wrong photo. For a standalone
    avatar; to embed one inside a larger custom card, use avatar_html()."""
    st.markdown(avatar_html(name, photo_url, size), unsafe_allow_html=True)
