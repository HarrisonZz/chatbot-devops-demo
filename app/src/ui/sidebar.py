# src/ui/sidebar.py
import streamlit as st
from dataclasses import dataclass
from src.config import AppConfig

@dataclass(frozen=True)
class AvatarSelection:
    user_avatar: str
    bot_avatar: str

def render_sidebar(cfg: AppConfig, conv_service) -> AvatarSelection:
    """
    渲染側邊欄，包含：
    1. Avatar 選擇
    2. 歷史會話列表

    :param cfg: AppConfig 實例
    :param conv_service: ConversationService 實例
    :return: AvatarSelection
    """
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

        # 歷史會話列表（新增功能）
        st.subheader("📜 Recent Sessions")

        if st.button("🆕 New Session", use_container_width=True):
            # 清空當前會話，創建新會話
            st.session_state.clear()
            st.rerun()

        st.markdown("---")

        # 獲取會話列表
        try:
            sessions = conv_service.list_sessions(limit=cfg.session_list_limit)

            if sessions:
                for session in sessions:
                    # 截斷標題顯示
                    title = session["session_title"]
                    if len(title) > 30:
                        title = title[:30] + "..."

                    # 格式化時間
                    created_at = session["created_at"][:19]  # 去掉毫秒

                    # 創建會話按鈕
                    if st.button(
                        f"{title}\n🕐 {created_at}",
                        key=session["session_id"],
                        use_container_width=True
                    ):
                        # 清空當前會話並加載選中的會話
                        st.session_state.clear()
                        st.session_state["load_session_id"] = session["session_id"]
                        st.rerun()
            else:
                st.info("No recent sessions")
        except Exception as e:
            st.warning(f"Could not load sessions: {str(e)}")

    return AvatarSelection(user_avatar=user_avatar, bot_avatar=bot_avatar)
