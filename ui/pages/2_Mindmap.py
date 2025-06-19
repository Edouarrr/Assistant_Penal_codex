"""Mind map visualization page."""

import json
import streamlit as st
from modules.mindmap import build_mindmap, export_mindmap_graphml
from core.memory_warming import load_all_summaries, build_entity_map


def main() -> None:
    st.header("Mindmap des entités")
    summaries = load_all_summaries("summaries")
    entity_map = build_entity_map(summaries)
    graph = build_mindmap(entity_map)
    st.write(f"Noeuds: {graph.number_of_nodes()}, Arêtes: {graph.number_of_edges()}")

    if st.button("Exporter GraphML"):
        path = export_mindmap_graphml(graph)
        with open(path, "rb") as f:
            st.download_button("Télécharger", f, file_name=path)

    # Display raw entity map for reference
    with st.expander("Voir la carte d'entités"):
        st.json(entity_map)


if __name__ == "__main__":
    main()
