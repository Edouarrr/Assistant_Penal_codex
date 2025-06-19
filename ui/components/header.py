"""Header component for the Streamlit app."""
from pathlib import Path
import streamlit as st


def render_header(use_columns: bool = True) -> str:
    """Render the app header with logo and firm name and return HTML.
    
    Args:
        use_columns: Si True, utilise st.columns pour la mise en page (par défaut).
                    Si False, génère tout en HTML pur.
    
    Returns:
        str: Le code HTML du header généré.
    """
    logo_path = Path("static/logo-steru.svg")
    
    if use_columns:
        # Approche avec colonnes Streamlit (Version 1)
        cols = st.columns([1, 8])
        html_parts = ["<header style='display:flex;align-items:center'>"]
        
        with cols[0]:
            if logo_path.exists():
                st.image(str(logo_path), use_container_width=True)
                html_parts.append(
                    f"<img src='{logo_path.as_posix()}' style='height:50px;margin-right:1rem'>"
                )
            else:
                st.write(":grey_question:")
                html_parts.append("<span>:grey_question:</span>")
                
        with cols[1]:
            text = "<h1 style='margin-bottom:0'>Cabinet Steru</h1>"
            st.markdown(text, unsafe_allow_html=True)
            html_parts.append(text)
            
        st.markdown("---")
        html_parts.append("</header>")
        html = "\n".join(html_parts)
        
    else:
        # Approche HTML pure (Version 2)
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


def render_header_simple() -> None:
    """Version simplifiée du header sans retour HTML."""
    logo_path = Path("static/logo-steru.svg")
    cols = st.columns([1, 8])
    
    with cols[0]:
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        else:
            st.write(":grey_question:")
            
    with cols[1]:
        st.markdown("<h1 style='margin-bottom:0'>Cabinet Steru</h1>", unsafe_allow_html=True)
        
    st.markdown("---")