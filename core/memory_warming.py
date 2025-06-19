"""Aggregate piece summaries to create an AI-friendly case brief."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any, Dict, Iterable, List

from .piece_synthesizer import PieceSummary


def _load_summary(path: str) -> PieceSummary:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PieceSummary(**data)


def load_all_summaries(directory: str) -> List[PieceSummary]:
    """Return a list of PieceSummary objects found in ``directory``."""
    summaries: List[PieceSummary] = []
    for name in os.listdir(directory):
        if name.endswith("_summary.json"):
            summaries.append(_load_summary(os.path.join(directory, name)))
    return summaries


def generate_brief(summaries: Iterable[PieceSummary], token_limit: int = 1800) -> str:
    """Generate a simple textual brief from a list of summaries."""
    parts: List[str] = []
    for summary in summaries:
        lines = [
            f"Document: {summary.sourcing.get('fichier_source', 'inconnu')}",
            summary.faits_essentiels,
            summary.incoherences_detectees,
        ]
        parts.append("\n".join(filter(None, lines)))
    brief = "\n\n".join(parts)
    words = brief.split()
    if len(words) > token_limit:
        words = words[:token_limit]
    return " ".join(words)


def _classify_entity(name: str) -> str:
    lowered = name.lower()
    if any(k in lowered for k in ["sarl", "sas", "sa", "inc", "corp", "company", "ltd"]):
        return "personnes_morales"
    return "personnes_physiques"


def build_entity_map(summaries: Iterable[PieceSummary]) -> Dict[str, Any]:
    entity_map: Dict[str, Any] = {
        "personnes_physiques": defaultdict(lambda: {"mentions": 0, "roles": set(), "documents": set()}),
        "personnes_morales": defaultdict(lambda: {"mentions": 0, "roles": set(), "documents": set()}),
        "relations": [],
    }

    for summary in summaries:
        for party in summary.parties_citees:
            entity_type = _classify_entity(party)
            info = entity_map[entity_type][party]
            info["mentions"] += 1
            info["documents"].add(summary.sourcing.get("fichier_source"))
        # Placeholder: relations detection would go here

    # Convert sets to lists
    for entity_type in ["personnes_physiques", "personnes_morales"]:
        for party, info in entity_map[entity_type].items():
            info["documents"] = list(info["documents"])
            info["roles"] = list(info["roles"])

    entity_map["personnes_physiques"] = dict(entity_map["personnes_physiques"])
    entity_map["personnes_morales"] = dict(entity_map["personnes_morales"])
    return entity_map


def save_entity_map(entity_map: Dict[str, Any], dossier: str, base_dir: str = "summaries") -> str:
    dossier_dir = os.path.join(base_dir, dossier)
    os.makedirs(dossier_dir, exist_ok=True)
    path = os.path.join(dossier_dir, "entity_map.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entity_map, f, ensure_ascii=False, indent=2)
    return path


__all__ = [
    "load_all_summaries",
    "generate_brief",
    "build_entity_map",
    "save_entity_map",
]
