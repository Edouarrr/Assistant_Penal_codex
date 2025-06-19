"""Streamlit interface for Assistant Penal Codex."""

from pathlib import Path
import streamlit as st

from ui.components.header import render_header
from ui import styles


def main() -> None:
    st.set_page_config(page_title="Assistant Penal Codex", layout="wide")
    st.markdown(styles.INTER_FONTS_CSS, unsafe_allow_html=True)

    render_header()

    tabs = st.tabs(["Chronologie", "Mindmap", "Dashboard"])
    for name, tab in zip(["Chronologie", "Mindmap", "Dashboard"], tabs):
        with tab:
            st.write(f"Contenu de l'onglet {name}")

    if hasattr(st, "command_palette"):
        st.command_palette({"placeholder": lambda: None})


if __name__ == "__main__":
    main()
