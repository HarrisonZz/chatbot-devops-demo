# src/ui/chat.py
import streamlit as st
from dataclasses import dataclass

@dataclass
class ChatMessage:
    role: str
    content: str

def init_session() -> None:
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {"role": "assistant", "content": "Hello! I'm an AI Chat Robot. You can configure avatars in the sidebar."}
        ]

def render_history(user_avatar: str, bot_avatar: str) -> None:
    for msg in st.session_state.messages:
        avatar = user_avatar if msg["role"] == "user" else bot_avatar
        st.chat_message(msg["role"], avatar=avatar).write(msg["content"])

def handle_input(
    *,
    user_avatar: str,
    bot_avatar: str,
    on_user_prompt,   # callable(prompt)->str
) -> None:
    prompt = st.chat_input("Ask me anything about DevOps...")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user", avatar=user_avatar).write(prompt)

    with st.chat_message("assistant", avatar=bot_avatar):
        with st.spinner("Thinking..."):
            response_text = on_user_prompt(prompt)
            st.write(response_text)

    st.session_state.messages.append({"role": "assistant", "content": response_text})
