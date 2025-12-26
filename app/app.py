# app.py
from src.config import AppConfig
from src.services.logging import get_logger
from src.services.bedrock import get_bedrock_client, call_bedrock
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

render_header(cfg)
avatars = render_sidebar(cfg)

init_session()
render_history(avatars.user_avatar, avatars.bot_avatar)

def on_user_prompt(prompt: str) -> str:

    with tracer.start_as_current_span("generate_response", context=Context()) as span:
        
        span.set_attribute("gen_ai.prompt", prompt)
        return call_bedrock(
            prompt,
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
)
