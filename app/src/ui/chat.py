# src/ui/chat.py
import streamlit as st
from dataclasses import dataclass
from typing import Optional

@dataclass
class ChatMessage:
    role: str
    content: str

def init_session(conv_service, session_id: Optional[str] = None) -> str:
    """
    初始化會話
    - 如果提供 session_id，從 DynamoDB 加載歷史消息
    - 否則創建新會話

    :param conv_service: ConversationService 實例
    :param session_id: 可選的會話 ID（用於加載歷史會話）
    :return: 當前會話 ID
    """
    if "session_id" not in st.session_state:
        if session_id:
            # 加載歷史會話
            st.session_state["session_id"] = session_id
            messages = conv_service.load_session(session_id)
            if messages:
                st.session_state["messages"] = messages
            else:
                # 加載失敗，創建新會話
                st.session_state["session_id"] = conv_service.create_session()
                st.session_state["messages"] = [
                    {"role": "assistant", "content": "Hello! I'm an AI Chat Robot. You can configure avatars in the sidebar."}
                ]
                # 保存初始消息到 DynamoDB
                conv_service.save_message(
                    session_id=st.session_state["session_id"],
                    message_index=0,
                    role="assistant",
                    content="Hello! I'm an AI Chat Robot. You can configure avatars in the sidebar."
                )
        else:
            # 創建新會話
            st.session_state["session_id"] = conv_service.create_session()
            st.session_state["messages"] = [
                {"role": "assistant", "content": "Hello! I'm an AI Chat Robot. You can configure avatars in the sidebar."}
            ]
            # 保存初始消息到 DynamoDB
            conv_service.save_message(
                session_id=st.session_state["session_id"],
                message_index=0,
                role="assistant",
                content="Hello! I'm an AI Chat Robot. You can configure avatars in the sidebar."
            )

    return st.session_state["session_id"]

def render_history(user_avatar: str, bot_avatar: str) -> None:
    """渲染對話歷史"""
    for msg in st.session_state.messages:
        avatar = user_avatar if msg["role"] == "user" else bot_avatar
        st.chat_message(msg["role"], avatar=avatar).write(msg["content"])

def handle_input(
    *,
    user_avatar: str,
    bot_avatar: str,
    on_user_prompt,   # callable(prompt)->str
    conv_service,     # 新增：DynamoDB 服務
) -> None:
    """處理用戶輸入並保存到 DynamoDB"""
    prompt = st.chat_input("Ask me anything about DevOps...")
    if not prompt:
        return

    session_id = st.session_state["session_id"]
    message_index = len(st.session_state.messages)

    # 保存用戶消息到 session state
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user", avatar=user_avatar).write(prompt)

    # 持久化用戶消息到 DynamoDB
    # 如果是第一條用戶消息 (message_index == 1)，設置會話標題
    session_title = prompt[:50] if message_index == 1 else None
    conv_service.save_message(
        session_id=session_id,
        message_index=message_index,
        role="user",
        content=prompt,
        session_title=session_title
    )

    with st.chat_message("assistant", avatar=bot_avatar):
        with st.spinner("Thinking..."):
            response_text = on_user_prompt(prompt)
            st.write(response_text)

    # 保存助手回應到 session state
    st.session_state.messages.append({"role": "assistant", "content": response_text})

    # 持久化助手回應到 DynamoDB
    conv_service.save_message(
        session_id=session_id,
        message_index=message_index + 1,
        role="assistant",
        content=response_text
    )
