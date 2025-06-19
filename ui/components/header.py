"""Header component for the Streamlit app."""

from pathlib import Path
import streamlit as st


def render_header() -> str:
    """Render the app header with logo and firm name."""
    logo_path = Path("static/logo-steru.svg")
    if logo_path.exists():
        logo_html = f"<img src='{logo_path.as_posix()}' style='width:100%'>"
    else:
        logo_html = ":grey_question:"

    html = (
        "<header>"
        "<div style='display:flex;align-items:center'>"
        f"<div style='flex:1'>{logo_html}</div>"
        "<div style='flex:8'>"
        "<h1 style='margin-bottom:0'>Cabinet Steru</h1>"
        "<hr>"
        "</div>"
        "</div>"
        "</header>"
    )
    st.markdown(html, unsafe_allow_html=True)
    return html
