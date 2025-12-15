from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    page_title: str = "Simple AI Chatbot"
    page_icon: str = "🤖"
    layout: str = "centered"

    css_path: str = "static/style.css"
    header_html_path: str = "static/header.html"

    user_avatar_path: str = "static/cat.jpg"
    bot_avatar_path: str = "static/bot_icon.jpg"

    aws_region: str = "ap-northeast-1"
    model_id: str = "amazon.nova-lite-v1:0"

    max_tokens: int = 1000
    temperature: float = 0.7
