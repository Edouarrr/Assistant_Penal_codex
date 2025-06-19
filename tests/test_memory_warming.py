import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.memory_warming import generate_brief
from core.piece_synthesizer import PieceSummary


def test_generate_brief_respects_token_limit():
    summary = PieceSummary(
        metadata={},
        parties_citees=[],
        faits_essentiels="word " * 10,
        incoherences_detectees="",
        sourcing={"fichier_source": "file.txt"},
    )

    brief = generate_brief([summary], token_limit=5)
    assert len(brief.split()) == 5
    assert brief.startswith("Document: file.txt")
