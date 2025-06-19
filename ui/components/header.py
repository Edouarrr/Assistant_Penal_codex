"""Header component for the Streamlit app."""

from pathlib import Path
import streamlit as st


def render_header() -> str:
    """Render the app header with logo and firm name and return HTML."""
    logo_path = Path("static/logo-steru.svg")

    html_parts = ["<header style='display:flex;align-items:center'>"]
    if logo_path.exists():
        html_parts.append(
            f"<img src='{logo_path.as_posix()}' style='height:50px;margin-right:1rem'>"
        )
    else:
        html_parts.append("<span>:grey_question:</span>")
    html_parts.append("<h1 style='margin-bottom:0'>Cabinet Steru</h1>")
    html_parts.append("</header>")
    html = "\n".join(html_parts)

    st.markdown(html, unsafe_allow_html=True)
    st.markdown("---")
    return html
