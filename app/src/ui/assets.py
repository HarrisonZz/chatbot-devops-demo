from pathlib import Path
import streamlit as st
import requests

def load_css_link(url: str) -> None:
    st.markdown(f'<link rel="stylesheet" href="{url}">', unsafe_allow_html=True)

def load_html_link(url: str) -> None:
    st.markdown(
        f"""
<iframe
  src="{url}"
  style="width: 100%; border: 0; height: 160px; display:block;"
  loading="lazy"
></iframe>
""",
        unsafe_allow_html=True,
    )

@st.cache_data(ttl=60)
def fetch_text(url: str) -> str:
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text
