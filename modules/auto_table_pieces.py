import re
from typing import List, Dict
from pathlib import Path

from docx import Document


def extract_pieces_from_docx(file_path: str) -> List[Dict[str, str]]:
    document = Document(file_path)
    pattern = re.compile(r"Pi[eè]ce\s*(\d+)", re.IGNORECASE)
    pieces: List[Dict[str, str]] = []

    for para in document.paragraphs:
        match = pattern.search(para.text)
        if not match:
            continue
        numero = match.group(1)
        titre = para.text[match.end():].strip() or ""
        pieces.append({
            "numero": numero,
            "titre": titre,
            "date": "",
            "page": "",
        })
    return pieces


__all__ = ["extract_pieces_from_docx"]
