# app.py
import streamlit as st
from src.config import AppConfig
from src.services.logging import get_logger
from src.services.bedrock import get_bedrock_client, call_bedrock
from src.services.dynamodb_service import ConversationService
from src.ui.layout import configure_page, render_header
from src.ui.sidebar import render_sidebar
from opentelemetry import trace
from opentelemetry.context import Context
from src.ui.chat import init_session, render_history, handle_input

cfg = AppConfig()

# ⚠️ must be first Streamlit call
configure_page(cfg)

logger = get_logger()
client = get_bedrock_client(cfg.aws_region)

tracer = trace.get_tracer(__name__)

# 初始化 DynamoDB 服務
try:
    conv_service = ConversationService(
        table_name=cfg.dynamodb_table_name,
        region=cfg.aws_region
    )
except Exception as e:
    logger.error(f"Failed to initialize ConversationService: {e}")
    st.error("Failed to initialize conversation service. Please check configuration.")
    st.stop()

render_header(cfg)
avatars = render_sidebar(cfg, conv_service)

# 檢查是否需要加載歷史會話
load_session_id = st.session_state.pop("load_session_id", None)
current_session_id = init_session(conv_service, session_id=load_session_id)

render_history(avatars.user_avatar, avatars.bot_avatar)

def build_full_context(new_prompt: str) -> str:
    """
    將 session_state 中的對話紀錄轉換為 Claude 格式的 Prompt
    """
    formatted_history = ""

    # 從 session_state 讀取歷史訊息 (預設為空 list)
    messages = st.session_state.get("messages", [])

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        # 依照 Claude 建議的 Prompt 格式拼接 (Human / Assistant)
        if role == "user":
            formatted_history += f"\n\nHuman: {content}"
        elif role == "assistant":
            formatted_history += f"\n\nAssistant: {content}"

    # 最後加上使用者這次的新問題，並預留 Assistant 的回答空間
    formatted_history += f"\n\nHuman: {new_prompt}\n\nAssistant:"
    return formatted_history

def on_user_prompt(prompt: str) -> str:
    """處理用戶輸入並調用 Bedrock"""
    # 這裡呼叫上面的 helper function 取得「包含歷史的完整 Prompt」
    full_context_prompt = build_full_context(prompt)

    with tracer.start_as_current_span("generate_response", context=Context()) as span:

        # 記錄使用者當下的輸入 (方便除錯)
        span.set_attribute("gen_ai.prompt", prompt)
        span.set_attribute("gen_ai.session_id", current_session_id)

        return call_bedrock(
            full_context_prompt, # 👈 關鍵修改：傳送完整歷史，而不是只有 prompt
            client=client,
            model_id=cfg.model_id,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            logger=logger,
        )

handle_input(
    user_avatar=avatars.user_avatar,
    bot_avatar=avatars.bot_avatar,
    on_user_prompt=on_user_prompt,
    conv_service=conv_service,
)
