import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import hashlib

from core.piece_synthesizer import PieceSynthesizer, _simple_embedding


def test_create_summary_generates_expected_fields():
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

    expected_hash = f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
    expected_embedding = _simple_embedding(text)

    assert summary.metadata == metadata
    assert summary.parties_citees == parties
    assert summary.faits_essentiels == faits
    assert summary.incoherences_detectees == incoherences
    assert summary.sourcing == sourcing
    assert summary.hash_content == expected_hash
    assert summary.embeddings_pre_calcules == expected_embedding
