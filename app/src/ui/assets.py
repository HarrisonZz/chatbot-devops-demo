from pathlib import Path
import streamlit as st

def load_css(path: str) -> None:
    p = Path(path)
    if not p.exists():
        st.error(f"找不到 CSS 檔案: {path}")
        return
    st.markdown(f"<style>{p.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

def load_html(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: Could not find HTML file at {path}"
    return p.read_text(encoding="utf-8")
