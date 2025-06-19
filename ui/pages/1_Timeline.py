"""Timeline visualization page."""

import streamlit as st
from modules.timeline_builder import (
    load_timeline_events,
    build_timeline,
    export_timeline_html,
)


def main() -> None:
    st.header("Chronologie du dossier")
    events = load_timeline_events()
    fig = build_timeline(events)
    st.plotly_chart(fig, use_container_width=True)
    if st.button("Exporter en HTML"):
        path = export_timeline_html(fig)
        with open(path, "rb") as f:
            st.download_button("Télécharger", f, file_name=path)


if __name__ == "__main__":
    main()
