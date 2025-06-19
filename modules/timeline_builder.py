from __future__ import annotations

"""Utilities to build a simple timeline visualization."""

from pathlib import Path
from typing import List, Dict, Any

import plotly.express as px

from core.memory_warming import load_all_summaries


def load_timeline_events(summaries_dir: str = "summaries") -> List[Dict[str, Any]]:
    """Load events from saved summaries.

    Each summary may include a ``date`` field in its metadata. This
    function converts those into events that can be plotted on a
    timeline.
    """
    events: List[Dict[str, Any]] = []
    for summary in load_all_summaries(summaries_dir):
        meta = summary.metadata or {}
        date = meta.get("date") or meta.get("timestamp")
        if date:
            events.append({
                "Document": summary.sourcing.get("fichier_source", "inconnu"),
                "Start": date,
                "End": date,
            })
    return events


def build_timeline(events: List[Dict[str, Any]]):
    """Return a Plotly timeline figure for the given events."""
    if not events:
        return px.timeline()
    fig = px.timeline(events, x_start="Start", x_end="End", y="Document")
    fig.update_yaxes(autorange="reversed")
    return fig


def export_timeline_html(fig, path: str = "timeline.html") -> str:
    """Export the timeline figure to an HTML file."""
    fig.write_html(path)
    return str(Path(path))


__all__ = ["load_timeline_events", "build_timeline", "export_timeline_html"]
