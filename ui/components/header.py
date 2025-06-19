"""Header component for the Streamlit app."""
from pathlib import Path
import streamlit as st

def render_header(use_columns: bool = True, style: str = "default") -> str:
    """Render the app header with logo and firm name."""
    
    # Version simplifiée sans image pour éviter les erreurs
    html = """
    <div style='background-color: #0a84ff; padding: 20px; margin: -1rem -1rem 2rem -1rem;'>
        <h1 style='color: white; margin: 0; text-align: center;'>
            ⚖️ CABINET STERU BARATTE AARPI
        </h1>
        <p style='color: white; text-align: center; margin: 5px 0 0 0;'>
            Assistant IA - Droit pénal des affaires
        </p>
    </div>
    """
    
    st.markdown(html, unsafe_allow_html=True)
    
    return html


def render_header_simple() -> None:
    """Version simple du header."""
    render_header()


def render_header_legacy() -> str:
    """Version legacy du header."""
    return render_header()


def render_header_compact() -> str:
    """Version compacte du header."""
    return render_header()
