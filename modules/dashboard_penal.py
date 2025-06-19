from __future__ import annotations

"""Simple dashboard data aggregation."""

from pathlib import Path
from typing import Dict, Any
import json

from core.memory_warming import load_all_summaries


def compile_dashboard_metrics(summaries_dir: str = "summaries") -> Dict[str, Any]:
    """Aggregate basic metrics from stored summaries."""
    summaries = load_all_summaries(summaries_dir)
    parties = {p for s in summaries for p in s.parties_citees}
    metrics = {
        "document_count": len(summaries),
        "unique_parties": len(parties),
    }
    return metrics


def export_dashboard_json(metrics: Dict[str, Any], path: str = "dashboard.json") -> str:
    """Save dashboard metrics as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    return str(Path(path))


__all__ = ["compile_dashboard_metrics", "export_dashboard_json"]
