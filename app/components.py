"""Small reusable UI pieces shared across pages."""

import hashlib

import streamlit as st

AVATAR_COLORS = [
    "#EC1C24", "#004BA0", "#FDB913", "#3A225D", "#EA1A85",
    "#17479E", "#FF822A", "#1B2133", "#A72056", "#0D3692",
]


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
