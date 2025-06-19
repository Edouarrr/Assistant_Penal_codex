import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.piece_synthesizer import PieceSynthesizer, PieceSummary, _hash_text


def test_create_summary(tmp_path):
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

    assert isinstance(summary, PieceSummary)
    assert summary.metadata == metadata
    assert summary.parties_citees == parties
    assert summary.faits_essentiels == faits
    assert summary.incoherences_detectees == incoherences
    assert summary.sourcing == sourcing
    assert summary.hash_content == f"sha256:{_hash_text(text)}"
    assert len(summary.embeddings_pre_calcules) == 10
    assert all(isinstance(v, float) for v in summary.embeddings_pre_calcules)
