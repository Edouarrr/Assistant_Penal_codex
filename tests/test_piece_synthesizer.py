import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import hashlib
from core.piece_synthesizer import PieceSynthesizer, PieceSummary, _simple_embedding, _hash_text


def test_create_summary_generates_expected_fields():
    """Test de la version codex : vérification des champs générés."""
    synthesizer = PieceSynthesizer()
    text = "Hello world"
    metadata = {"title": "Test"}
    parties = ["Alice", "Bob"]
    faits = "Important facts"
    incoherences = "None"
    sourcing = {"fichier_source": "doc.txt"}
    
    summary = synthesizer.create_summary(
        text,
        metadata,
        parties,
        faits,
        incoherences,
        sourcing,
    )
    
    # Vérifications version codex
    expected_hash = f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
    expected_embedding = _simple_embedding(text)
    
    assert summary.metadata == metadata
    assert summary.parties_citees == parties
    assert summary.faits_essentiels == faits
    assert summary.incoherences_detectees == incoherences
    assert summary.sourcing == sourcing
    assert summary.hash_content == expected_hash
    assert summary.embeddings_pre_calcules == expected_embedding


def test_create_summary_with_tmp_path(tmp_path):
    """Test de la version main : utilisation avec répertoire temporaire."""
    synth = PieceSynthesizer(summaries_dir=str(tmp_path))
    text = "Exemple de texte pour le résumé."
    metadata = {"foo": "bar"}
    parties = ["Alice", "ACME SARL"]
    faits = "Faits importants"
    incoherences = "Aucune"
    sourcing = {"fichier_source": "doc.pdf"}
    
    summary = synth.create_summary(
        text,
        metadata,
        parties,
        faits,
        incoherences,
        sourcing,
    )
    
    # Vérifications version main
    assert isinstance(summary, PieceSummary)
    assert summary.metadata == metadata
    assert summary.parties_citees == parties
    assert summary.faits_essentiels == faits
    assert summary.incoherences_detectees == incoherences
    assert summary.sourcing == sourcing
    assert summary.hash_content == f"sha256:{_hash_text(text)}"
    assert len(summary.embeddings_pre_calcules) == 10
    assert all(isinstance(v, float) for v in summary.embeddings_pre_calcules)


def test_create_summary_hash_consistency():
    """Test additionnel : cohérence entre les deux méthodes de calcul de hash."""
    text = "Test text for hash comparison"
    
    # Méthode 1 : hashlib direct
    hash1 = hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    # Méthode 2 : fonction _hash_text
    hash2 = _hash_text(text)
    
    assert hash1 == hash2, "Les deux méthodes de hash doivent produire le même résultat"


def test_simple_embedding_structure():
    """Test additionnel : vérification de la structure de l'embedding simple."""
    text = "Sample text for embedding"
    embedding = _simple_embedding(text)
    
    assert isinstance(embedding, list)
    assert len(embedding) == 10  # Attendu selon le test main
    assert all(isinstance(v, float) for v in embedding)
    assert all(0 <= v <= 1 for v in embedding), "Les valeurs d'embedding doivent être normalisées"


def test_save_and_load_summary(tmp_path):
    """Test additionnel : sauvegarde et chargement d'un résumé."""
    synth = PieceSynthesizer(summaries_dir=str(tmp_path))
    
    # Création du résumé
    summary = synth.create_summary(
        text="Test de sauvegarde",
        metadata={"test": True},
        parties_citees=["TestUser"],
        faits_essentiels="Faits de test",
        incoherences_detectees="",
        sourcing={"fichier_source": "test.txt"},
    )
    
    # Sauvegarde
    synth.save_summary(summary, "test_summary")
    
    # Vérification que le fichier existe
    summary_file = tmp_path / "test_summary.json"
    assert summary_file.exists()
    
    # Chargement et vérification
    import json
    with open(summary_file, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)
    
    assert loaded_data["metadata"] == {"test": True}
    assert loaded_data["parties_citees"] == ["TestUser"]
    assert loaded_data["faits_essentiels"] == "Faits de test"