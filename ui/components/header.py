"""Header component for the Streamlit app."""

from pathlib import Path
import streamlit as st


def render_header() -> str:
    """Render the app header with logo and firm name."""
    logo_path = Path("static/logo-steru.svg")
    if logo_path.exists():
        logo_html = f"<img src='{logo_path.as_posix()}' style='height:50px'>"
    else:
        logo_html = ":grey_question:"
    html = (
        "<header><div style='display:flex;align-items:center;gap:1rem;'>"
        f"{logo_html}<h1 style='margin-bottom:0'>Cabinet Steru</h1>"
        "</div><hr/></header>"
    )
    st.markdown(html, unsafe_allow_html=True)
    return html
