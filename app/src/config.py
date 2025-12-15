from dataclasses import dataclass, field
import os
import streamlit as st

def get_url_from_env() -> str:
    """Helper function to fetch URL"""
    
    # 其次讀取環境變數 (Docker / Local)
    # 如果都沒設，回傳空字串 (代表使用相對路徑/本地路徑)
    return os.getenv("CLOUDFRONT_STATIC_URL", "").rstrip("/")

@dataclass(frozen=True)
class AppConfig:
    page_title: str = "Simple AI Chatbot"
    page_icon: str = "🤖"
    layout: str = "centered"

    aws_region: str = "ap-northeast-1"
    model_id: str = "amazon.nova-lite-v1:0"

    max_tokens: int = 1000
    temperature: float = 0.7

    assets_base_url: str = field(default_factory=get_url_from_env)

    @property
    def css_url(self) -> str:
        return f"{self.assets_base_url}/style.css"

    @property
    def header_html_url(self) -> str:
        return f"{self.assets_base_url}/header.html"

    @property
    def user_avatar_url(self) -> str:
        return f"{self.assets_base_url}/cat.jpg"

    @property
    def bot_avatar_url(self) -> str:
        return f"{self.assets_base_url}/bot_icon.jpg"
