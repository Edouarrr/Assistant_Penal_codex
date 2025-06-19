from __future__ import annotations

"""Générateur de lettres personnalisées.

Ce module remplit un modèle Word avec des données fournies et
retourne le chemin du fichier généré. Il s'appuie sur ``docxtpl``
qui doit être installé séparément.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate


TEMPLATE_PATH = Path("templates/modele_lettre.docx")


def generate_letter(
    destinataire: str,
    objet: str,
    contenu_md: str,
    output_path: str | Path = "lettre_steru.docx",
) -> Path:
    """Remplir le modèle Word et enregistrer le résultat.

    Parameters
    ----------
    destinataire:
        Nom ou raison sociale du destinataire.
    objet:
        Objet de la lettre.
    contenu_md:
        Corps de la lettre au format Markdown ou texte brut.
    output_path:
        Chemin du fichier résultant. ``lettre_steru.docx`` par défaut.
    """

    doc = DocxTemplate(TEMPLATE_PATH)

    context: dict[str, Any] = {
        "date": datetime.today().strftime("%d/%m/%Y"),
        "destinataire": destinataire,
        "objet": objet,
        "paragraphe_libre": contenu_md,
    }

    doc.render(context)

    output_path = Path(output_path)
    doc.save(str(output_path))
    return output_path
