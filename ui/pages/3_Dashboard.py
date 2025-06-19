"""Basic dashboard page."""

import streamlit as st
from modules.dashboard_penal import (
    compile_dashboard_metrics,
    export_dashboard_json,
)


def main() -> None:
    st.header("Dashboard Pénal")
    metrics = compile_dashboard_metrics()
    st.json(metrics)

    if st.button("Exporter JSON"):
        path = export_dashboard_json(metrics)
        with open(path, "rb") as f:
            st.download_button("Télécharger", f, file_name=path)


if __name__ == "__main__":
    main()
