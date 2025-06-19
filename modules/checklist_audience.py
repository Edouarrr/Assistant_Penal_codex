import json
from dataclasses import dataclass, field
from typing import List
from pathlib import Path


@dataclass
class ChecklistItem:
    task: str
    done: bool = False


@dataclass
class Checklist:
    dossier: str
    items: List[ChecklistItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dossier": self.dossier,
            "items": [{"task": i.task, "done": i.done} for i in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checklist":
        items = [ChecklistItem(**i) for i in data.get("items", [])]
        return cls(dossier=data.get("dossier", ""), items=items)


def save_checklist(checklist: Checklist, dossier_id: str, base_dir: str = "checklists") -> str:
    Path(base_dir).mkdir(exist_ok=True)
    path = Path(base_dir) / f"{dossier_id}_todo.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(checklist.to_dict(), f, ensure_ascii=False, indent=2)
    return str(path)


def load_checklist(dossier_id: str, base_dir: str = "checklists") -> Checklist:
    path = Path(base_dir) / f"{dossier_id}_todo.json"
    if not path.exists():
        return Checklist(dossier=dossier_id)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Checklist.from_dict(data)


def checklist_to_markdown(checklist: Checklist) -> str:
    lines = [f"# Checklist {checklist.dossier}"]
    for item in checklist.items:
        box = "[x]" if item.done else "[ ]"
        lines.append(f"- {box} {item.task}")
    return "\n".join(lines)


__all__ = [
    "ChecklistItem",
    "Checklist",
    "save_checklist",
    "load_checklist",
    "checklist_to_markdown",
]
