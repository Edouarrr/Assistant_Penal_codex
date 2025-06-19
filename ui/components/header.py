"""Header component for the Streamlit app."""

from pathlib import Path
import streamlit as st


def render_header() -> str:
    """Render the app header with logo and firm name."""
    logo_path = Path("static/logo-steru.svg")
    cols = st.columns([1, 8])
    html = ["<header>"]
    with cols[0]:
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        else:
            st.write(":grey_question:")
    with cols[1]:
        text = "<h1 style='margin-bottom:0'>Cabinet Steru</h1>"
        st.markdown(text, unsafe_allow_html=True)
        st.markdown("---")
        html.append(text)
    html.append("</header>")
    return "\n".join(html)
