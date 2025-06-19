"""Streamlit interface for Assistant Penal Codex."""

from pathlib import Path
import streamlit as st

from ui.components.header import render_header
from ui import styles


def main() -> None:
    """Render the Streamlit UI."""
    st.set_page_config(page_title="Assistant Penal Codex", layout="wide")
    st.markdown(styles.INTER_FONTS_CSS, unsafe_allow_html=True)

    render_header()

    with st.form("input_form", clear_on_submit=False):
        user_text = st.text_area("Votre question", key="user_text", height=100)
        submitted = st.form_submit_button("Envoyer")
        if submitted:
            st.session_state["submitted_text"] = user_text
            st.toast("AI response ready", icon="✅")

    TABS = [
        "Chronologie",
        "Contradictions",
        "Fiches de synthèse",
        "IA",
        "Rédaction",
        "Préparation client",
        "Mindmap",
        "Checklist audience",
        "Lettre",
        "Logs",
    ]
    pages = st.tabs(TABS)
    for name, tab in zip(TABS, pages):
        with tab:
            st.write(f"Contenu de l'onglet {name}")

    pdf_file = Path("sample.pdf")
    if pdf_file.exists():
        pdf_html = (
            f'<iframe src="{pdf_file.as_posix()}#page=1" '
            'width="350" height="600"></iframe>'
        )
        st.sidebar.components.v1.html(pdf_html, height=600)

    st.toast("Vectorization complete", icon="🎉")


if __name__ == "__main__":
    main()
