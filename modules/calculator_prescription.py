import datetime
import yaml
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class PrescriptionResult:
    echeance_theorique: datetime.date
    date_limite: datetime.date
    statut: str
    couleur: str
    timeline: str


def _load_settings(path: str = "config/prescription_settings.yaml") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_timeline(start: datetime.date, end: datetime.date, today: datetime.date) -> str:
    total = (end - start).days
    elapsed = (today - start).days
    ratio = min(max(elapsed / total, 0.0), 1.0) if total > 0 else 1.0
    bar_length = 20
    filled = int(bar_length * ratio)
    bar = "█" * filled + "─" * (bar_length - filled)
    return f"|{bar}| {int(ratio*100):02d}%"


def calculate_prescription(date_faits: datetime.date,
                           dernier_acte: datetime.date,
                           infraction: str,
                           recidive: bool = False,
                           settings_path: str = "config/prescription_settings.yaml") -> PrescriptionResult:
    settings = _load_settings(settings_path)
    delays = settings.get("infraction_delays", {})
    delay_years = delays.get(infraction, 0)
    if recidive:
        delay_years *= settings.get("recidive_multiplier", 1)

    def _add_years(d: datetime.date, years: int) -> datetime.date:
        try:
            return d.replace(year=d.year + years)
        except ValueError:  # leap day
            return d.replace(month=2, day=28, year=d.year + years)

    echeance_theorique = _add_years(date_faits, delay_years)
    date_limite = _add_years(dernier_acte, delay_years)

    today = datetime.date.today()
    threshold = settings.get("near_threshold_days", 30)

    if today > date_limite:
        statut = "dépasse"
        couleur = "red"
    elif (date_limite - today).days <= threshold:
        statut = "proche"
        couleur = "orange"
    else:
        statut = "dans délais"
        couleur = "green"

    timeline = _build_timeline(date_faits, date_limite, today)

    return PrescriptionResult(
        echeance_theorique=echeance_theorique,
        date_limite=date_limite,
        statut=statut,
        couleur=couleur,
        timeline=timeline,
    )


__all__ = ["calculate_prescription", "PrescriptionResult"]
