import streamlit as st
from src.config import AppConfig
from src.ui.assets import *

def configure_page(cfg: AppConfig) -> None:
    # ⚠️ 必須是第一個 Streamlit 指令
    st.set_page_config(page_title=cfg.page_title, page_icon=cfg.page_icon, layout=cfg.layout)

def render_header(cfg: AppConfig) -> None:
    load_css_link(cfg.css_url)

    header_html = fetch_text(cfg.header_html_url)
    st.markdown(header_html, unsafe_allow_html=True)
