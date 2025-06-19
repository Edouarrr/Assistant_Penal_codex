import difflib
from dataclasses import dataclass
from typing import List
from pathlib import Path

from docx import Document


def _read_file(path: str) -> List[str]:
    ext = Path(path).suffix.lower()
    if ext == ".docx":
        doc = Document(path)
        return [p.text for p in doc.paragraphs]
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


@dataclass
class DiffObject:
    html: str
    markdown: str


def compare_docs(file1: str, file2: str) -> DiffObject:
    lines1 = _read_file(file1)
    lines2 = _read_file(file2)

    diff = difflib.ndiff(lines1, lines2)
    html_lines: List[str] = []
    md_lines: List[str] = []
    for line in diff:
        if line.startswith("+"):
            text = line[2:]
            html_lines.append(f'<span style="background:#c6f6d5">{text}</span>')
            md_lines.append(f'🟩 {text}')
        elif line.startswith("-"):
            text = line[2:]
            html_lines.append(f'<span style="background:#feb2b2">{text}</span>')
            md_lines.append(f'🟥 {text}')
        else:
            text = line[2:]
            html_lines.append(text)
            md_lines.append(text)
    html = "<br>".join(html_lines)
    md = "\n".join(md_lines)
    return DiffObject(html=html, markdown=md)


__all__ = ["compare_docs", "DiffObject"]
