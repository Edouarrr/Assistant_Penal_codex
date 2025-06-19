from __future__ import annotations

"""Simple functions to create a mind map of entities."""

from pathlib import Path
from typing import Dict, Any

import networkx as nx


def build_mindmap(entity_map: Dict[str, Any]) -> nx.Graph:
    """Return a NetworkX graph representing the entity map."""
    g = nx.Graph()
    for name in entity_map.get("personnes_physiques", {}):
        g.add_node(name, type="personne_physique")
    for name in entity_map.get("personnes_morales", {}):
        g.add_node(name, type="personne_morale")
    for rel in entity_map.get("relations", []):
        src = rel.get("source")
        dst = rel.get("target")
        if src and dst:
            g.add_edge(src, dst, label=rel.get("relation", ""))
    return g


def export_mindmap_graphml(graph: nx.Graph, path: str = "mindmap.graphml") -> str:
    """Export the mind map to GraphML format."""
    nx.write_graphml(graph, path)
    return str(Path(path))


__all__ = ["build_mindmap", "export_mindmap_graphml"]
