"""Utilities for generating structured summaries for legal documents."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional


def _ensure_summaries_dir() -> str:
    """Ensure that the summaries directory exists."""
    summaries_dir = os.path.join(os.getcwd(), "summaries")
    os.makedirs(summaries_dir, exist_ok=True)
    return summaries_dir


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _simple_embedding(text: str, dimensions: int = 10) -> List[float]:
    """Return a very naive embedding based on hashing."""
    hashed = _hash_text(text)
    chunk_size = len(hashed) // dimensions
    vector: List[float] = []
    for i in range(dimensions):
        chunk = hashed[i * chunk_size : (i + 1) * chunk_size]
        vector.append(int(chunk, 16) / 10 ** len(chunk))
    return vector


@dataclass
class PieceSummary:
    metadata: Dict[str, Any]
    parties_citees: List[str] = field(default_factory=list)
    faits_essentiels: str = ""
    incoherences_detectees: str = ""
    sourcing: Dict[str, Any] = field(default_factory=dict)
    hash_content: str = ""
    embeddings_pre_calcules: List[float] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def to_html(self) -> str:
        """Return a simple HTML representation of the summary."""
        html_lines = ["<html>", "<body>", "<h2>Résumé de pièce</h2>"]
        html_lines.append("<pre>" + self.to_json() + "</pre>")
        html_lines.extend(["</body>", "</html>"])
        return "\n".join(html_lines)


class PieceSynthesizer:
    """Create structured summaries for legal documents."""

    def __init__(self, summaries_dir: Optional[str] = None) -> None:
        self.summaries_dir = summaries_dir or _ensure_summaries_dir()

    def create_summary(
        self,
        text: str,
        metadata: Dict[str, Any],
        parties_citees: Iterable[str],
        faits_essentiels: str,
        incoherences_detectees: str,
        sourcing: Dict[str, Any],
    ) -> PieceSummary:
        hash_content = _hash_text(text)
        embeddings = _simple_embedding(text)
        summary = PieceSummary(
            metadata=metadata,
            parties_citees=list(parties_citees),
            faits_essentiels=faits_essentiels,
            incoherences_detectees=incoherences_detectees,
            sourcing=sourcing,
            hash_content=f"sha256:{hash_content}",
            embeddings_pre_calcules=embeddings,
        )
        return summary

    def save_summary(self, summary: PieceSummary, source_filename: str) -> str:
        """Persist the summary to the summaries directory."""
        base_name = os.path.splitext(os.path.basename(source_filename))[0]
        path = os.path.join(self.summaries_dir, f"{base_name}_summary.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(summary.to_json())
        return path

    def load_summary(self, path: str) -> PieceSummary:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PieceSummary(**data)


__all__ = ["PieceSynthesizer", "PieceSummary"]
