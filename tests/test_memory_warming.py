import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.memory_warming import generate_brief, build_entity_map
from core.piece_synthesizer import PieceSummary


def _summary(**kwargs):
    defaults = {
        "metadata": {},
        "parties_citees": [],
        "faits_essentiels": "",
        "incoherences_detectees": "",
        "sourcing": {},
        "hash_content": "",
        "embeddings_pre_calcules": [],
    }
    defaults.update(kwargs)
    return PieceSummary(**defaults)


def test_generate_brief_limits_tokens():
    summaries = [
        _summary(faits_essentiels="un " * 20, sourcing={"fichier_source": "a"}),
        _summary(faits_essentiels="deux " * 20, sourcing={"fichier_source": "b"}),
    ]
    brief = generate_brief(summaries, token_limit=5)
    assert len(brief.split()) <= 5
    assert "Document: a" in brief


def test_build_entity_map_classification():
    summaries = [
        _summary(parties_citees=["Alice", "ACME SARL"], sourcing={"fichier_source": "d1"}),
        _summary(parties_citees=["Alice"], sourcing={"fichier_source": "d2"}),
    ]
    entity_map = build_entity_map(summaries)

    alice = entity_map["personnes_physiques"]["Alice"]
    assert alice["mentions"] == 2
    assert set(alice["documents"]) == {"d1", "d2"}

    assert "ACME SARL" in entity_map["personnes_morales"]
