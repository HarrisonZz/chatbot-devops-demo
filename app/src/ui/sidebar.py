# src/ui/sidebar.py
import streamlit as st
from dataclasses import dataclass
from src.config import AppConfig

@dataclass(frozen=True)
class AvatarSelection:
    user_avatar: str
    bot_avatar: str

def render_sidebar(cfg: AppConfig) -> AvatarSelection:
    avatar_display_map = {
        cfg.user_avatar_url: "🐱",
        cfg.bot_avatar_url: "🤖",
        "👤": "👤",
        "🧠": "🧠",
        "👨‍💼": "👨‍💼",
        "🚀": "🚀",
        "🦄": "🦄",
    }

    def format_avatar_option(option: str) -> str:
        return avatar_display_map.get(option, option)

    with st.sidebar:
        st.header("⚙️ Settings")
        st.markdown("---")
        st.subheader("🖼️ Avatar Selection")

        user_avatar = st.selectbox(
            "Choose User Avatar:",
            options=[cfg.user_avatar_url, "👤", "👨‍💼", "🚀"],
            format_func=format_avatar_option,
            index=0,
        )

        bot_avatar = st.selectbox(
            "Choose Bot Avatar:",
            options=[cfg.bot_avatar_url, "🧠", "🦄"],
            format_func=format_avatar_option,
            index=0,
        )

        st.markdown("---")

    return AvatarSelection(user_avatar=user_avatar, bot_avatar=bot_avatar)
