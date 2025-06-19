import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.memory_warming import generate_brief, build_entity_map
from core.piece_synthesizer import PieceSummary


def _summary(**kwargs):
    """Helper function pour créer des PieceSummary avec des valeurs par défaut."""
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


def test_generate_brief_respects_token_limit():
    """Test de la version codex : vérification simple de la limite de tokens."""
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


def test_generate_brief_limits_tokens_multiple_summaries():
    """Test de la version main : vérification avec plusieurs résumés."""
    summaries = [
        _summary(faits_essentiels="un " * 20, sourcing={"fichier_source": "a"}),
        _summary(faits_essentiels="deux " * 20, sourcing={"fichier_source": "b"}),
    ]
    brief = generate_brief(summaries, token_limit=5)
    assert len(brief.split()) <= 5
    assert "Document: a" in brief


def test_generate_brief_handles_empty_summaries():
    """Test additionnel : gestion des résumés vides."""
    summaries = []
    brief = generate_brief(summaries, token_limit=10)
    assert brief == "" or len(brief.split()) <= 10


def test_build_entity_map_classification():
    """Test de classification des entités en personnes physiques et morales."""
    summaries = [
        _summary(parties_citees=["Alice", "ACME SARL"], sourcing={"fichier_source": "d1"}),
        _summary(parties_citees=["Alice"], sourcing={"fichier_source": "d2"}),
    ]
    entity_map = build_entity_map(summaries)
    
    # Vérifications pour Alice (personne physique)
    alice = entity_map["personnes_physiques"]["Alice"]
    assert alice["mentions"] == 2
    assert set(alice["documents"]) == {"d1", "d2"}
    
    # Vérifications pour ACME SARL (personne morale)
    assert "ACME SARL" in entity_map["personnes_morales"]
    acme = entity_map["personnes_morales"]["ACME SARL"]
    assert acme["mentions"] == 1
    assert acme["documents"] == ["d1"]


def test_build_entity_map_empty_input():
    """Test additionnel : construction d'une carte d'entités vide."""
    entity_map = build_entity_map([])
    assert "personnes_physiques" in entity_map
    assert "personnes_morales" in entity_map
    assert len(entity_map["personnes_physiques"]) == 0
    assert len(entity_map["personnes_morales"]) == 0