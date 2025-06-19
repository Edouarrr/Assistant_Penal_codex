from __future__ import annotations

import datetime as _dt
import io
import json
import logging
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Any, Optional

import requests
from google.api_core.exceptions import GoogleAPIError
from google.cloud import vision
from pdf2image import convert_from_path
from PyPDF2 import PdfMerger
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from src.get_sharepoint_token import get_token
from core.vector_juridique import VectorJuridique

RAW_DIR = Path("raw_documents")
OCR_DIR = Path("ocr_output")
LOG_FILE = Path("logs/ocr_errors.log")


def _setup_logging() -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.ERROR,
        format="%(asctime)s | %(message)s",
    )


def _log_error(file_path: Path, message: str, exc: Exception | None = None) -> None:
    logging.error("%s | %s | %s", file_path, message, exc)


def _normalize_segment(segment: str) -> str:
    normalized = unicodedata.normalize("NFD", segment)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^A-Za-z0-9_.-]", "", normalized)
    return normalized[:100]


def _sanitize_path(path: Path) -> Path:
    return Path(*(_normalize_segment(p) for p in path.parts))


class GraphClient:
    def __init__(self) -> None:
        self.site_id = os.environ.get("SHAREPOINT_SITE", "")
        self.drive_id = os.environ.get("SHAREPOINT_DRIVE", "")
        self._base = "https://graph.microsoft.com/v1.0"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {get_token()}"}

    def walk(self, item_id: str = "root", prefix: Path | None = None) -> Iterable[Tuple[Dict, Path]]:
        prefix = prefix or Path()
        url = f"{self._base}/drives/{self.drive_id}/items/{item_id}/children"
        while url:
            res = requests.get(url, headers=self._headers())
            res.raise_for_status()
            data = res.json()
            for entry in data.get("value", []):
                name = entry["name"]
                if entry.get("folder"):
                    yield from self.walk(entry["id"], prefix / name)
                else:
                    yield entry, prefix / name
            url = data.get("@odata.nextLink")

    def download(self, item: Dict, target: Path) -> None:
        url = f"{self._base}/drives/{self.drive_id}/items/{item['id']}/content"
        res = requests.get(url, headers=self._headers())
        res.raise_for_status()
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(res.content)

    def get_file_metadata(self, item_id: str) -> Dict[str, Any]:
        """Récupère les métadonnées détaillées d'un fichier."""
        url = f"{self._base}/drives/{self.drive_id}/items/{item_id}"
        res = requests.get(url, headers=self._headers())
        res.raise_for_status()
        
        data = res.json()
        
        # Extraire les métadonnées importantes
        metadata = {
            'name': data.get('name'),
            'size': data.get('size'),
            'created': data.get('createdDateTime'),
            'modified': data.get('lastModifiedDateTime'),
            'author': data.get('createdBy', {}).get('user', {}).get('displayName'),
            'last_modifier': data.get('lastModifiedBy', {}).get('user', {}).get('displayName'),
            'mime_type': data.get('file', {}).get('mimeType'),
            'web_url': data.get('webUrl')
        }
        
        return metadata

    def filter_by_author(self, author_name: str) -> List[Tuple[Dict, Path]]:
        """Filtre les fichiers par auteur."""
        filtered_files = []
        
        for item, path in self.walk():
            try:
                metadata = self.get_file_metadata(item['id'])
                if author_name.lower() in (metadata.get('author', '').lower() or 
                                          metadata.get('last_modifier', '').lower()):
                    filtered_files.append((item, path))
            except Exception as e:
                _log_error(path, f"Erreur lors de la récupération des métadonnées", e)
        
        return filtered_files

    def filter_by_date(self, days: int) -> List[Tuple[Dict, Path]]:
        """Filtre les fichiers modifiés dans les X derniers jours."""
        from datetime import timezone
        cutoff_date = _dt.datetime.now(timezone.utc) - _dt.timedelta(days=days)
        filtered_files = []
        
        for item, path in self.walk():
            try:
                modified_str = item.get('lastModifiedDateTime', '')
                if modified_str:
                    modified_date = _dt.datetime.fromisoformat(modified_str.rstrip('Z')).replace(tzinfo=timezone.utc)
                    if modified_date > cutoff_date:
                        filtered_files.append((item, path))
            except Exception as e:
                _log_error(path, f"Erreur lors du filtrage par date", e)
        
        return filtered_files


def _needs_download(item: Dict, local_path: Path) -> bool:
    if not local_path.exists():
        return True
    remote_time = _dt.datetime.fromisoformat(item["lastModifiedDateTime"].rstrip("Z"))
    local_time = _dt.datetime.fromtimestamp(local_path.stat().st_mtime)
    return remote_time > local_time


def _needs_ocr(local_path: Path) -> bool:
    out_txt = OCR_DIR / local_path.relative_to(RAW_DIR).with_suffix(".txt")
    out_pdf = OCR_DIR / local_path.relative_to(RAW_DIR).with_suffix(".pdf")
    return not out_txt.exists() or not out_pdf.exists()


def _ocr_file(path: Path) -> str:
    client = vision.ImageAnnotatorClient()
    texts: List[str] = []

    if path.suffix.lower() == ".pdf":
        pages = convert_from_path(path)
        for num, page in enumerate(pages, start=1):
            buf = io.BytesIO()
            page.save(buf, format="PNG")
            image = vision.Image(content=buf.getvalue())
            try:
                resp = client.document_text_detection(
                    image=image,
                    image_context={"language_hints": ["fr", "en"], "enable_auto_rotation": True},
                )
                if resp.error.message:
                    raise RuntimeError(resp.error.message)
            except GoogleAPIError:
                resp = client.text_detection(image=image)
                if resp.error.message:
                    raise RuntimeError(resp.error.message)
            texts.append(resp.full_text_annotation.text or "")
    else:
        with open(path, "rb") as fh:
            content = fh.read()
        image = vision.Image(content=content)
        try:
            resp = client.document_text_detection(
                image=image,
                image_context={"language_hints": ["fr", "en"], "enable_auto_rotation": True},
            )
            if resp.error.message:
                raise RuntimeError(resp.error.message)
        except GoogleAPIError:
            resp = client.text_detection(image=image)
            if resp.error.message:
                raise RuntimeError(resp.error.message)
        texts.append(resp.full_text_annotation.text or "")
    return "\n\n".join(texts)


def sync() -> None:
    _setup_logging()
    client = GraphClient()
    vectorizer = VectorJuridique()

    for item, rel in client.walk():
        sanitized_rel = _sanitize_path(rel)
        local = RAW_DIR / sanitized_rel

        if _needs_download(item, local):
            try:
                client.download(item, local)
            except Exception as exc:
                _log_error(local, "download failed", exc)
                continue

        if _needs_ocr(local):
            try:
                text = _ocr_file(local)
                txt_out = OCR_DIR / sanitized_rel.with_suffix(".txt")
                txt_out.parent.mkdir(parents=True, exist_ok=True)
                with open(txt_out, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception as exc:
                _log_error(local, "ocr failed", exc)
                continue

            try:
                vectorizer.process_pdf(str(local))
            except Exception as exc:
                _log_error(local, "vectorization failed", exc)


def sync_with_filters(author: str = None, days: int = None, specific_folders: List[str] = None) -> Dict[str, int]:
    """
    Synchronise avec des filtres spécifiques.
    
    Args:
        author: Filtrer par auteur (ex: "Edouard Steru")
        days: Fichiers modifiés dans les X derniers jours
        specific_folders: Liste des dossiers spécifiques à synchroniser
    
    Returns:
        Statistiques de synchronisation
    """
    _setup_logging()
    client = GraphClient()
    vectorizer = VectorJuridique()
    
    stats = {
        'files_processed': 0,
        'files_skipped': 0,
        'ocr_performed': 0,
        'errors': 0
    }
    
    # Récupérer les fichiers selon les filtres
    if author:
        files_to_process = client.filter_by_author(author)
        logging.info(f"Filtrage par auteur : {author}")
    elif days:
        files_to_process = client.filter_by_date(days)
        logging.info(f"Filtrage par date : {days} derniers jours")
    else:
        files_to_process = list(client.walk())
    
    # Filtrer par dossiers si spécifié
    if specific_folders:
        files_to_process = [
            (item, path) for item, path in files_to_process
            if any(folder in str(path) for folder in specific_folders)
        ]
    
    # Traiter chaque fichier
    for item, rel in files_to_process:
        sanitized_rel = _sanitize_path(rel)
        local = RAW_DIR / sanitized_rel
        
        try:
            # Télécharger si nécessaire
            if _needs_download(item, local):
                client.download(item, local)
                stats['files_processed'] += 1
            else:
                stats['files_skipped'] += 1
            
            # OCR si nécessaire
            if _needs_ocr(local):
                text = _ocr_file(local)
                txt_out = OCR_DIR / sanitized_rel.with_suffix(".txt")
                txt_out.parent.mkdir(parents=True, exist_ok=True)
                
                # Sauvegarder avec métadonnées
                metadata = client.get_file_metadata(item['id'])
                
                with open(txt_out, "w", encoding="utf-8") as f:
                    f.write(f"--- MÉTADONNÉES ---\n")
                    f.write(f"Fichier: {metadata['name']}\n")
                    f.write(f"Auteur: {metadata.get('author', 'Inconnu')}\n")
                    f.write(f"Modifié le: {metadata.get('modified', 'Inconnu')}\n")
                    f.write(f"--- CONTENU OCR ---\n\n")
                    f.write(text)
                
                stats['ocr_performed'] += 1
                
                # Vectoriser
                vectorizer.process_pdf(str(local))
                
        except Exception as e:
            _log_error(local, "Erreur lors du traitement", e)
            stats['errors'] += 1
    
    return stats


class SyncState:
    """Gère l'état de synchronisation pour éviter les re-traitements."""
    
    def __init__(self, state_file: str = "sync_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Charge l'état depuis le fichier."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            'last_sync': None,
            'processed_files': {},
            'deleted_files': []
        }
    
    def save_state(self):
        """Sauvegarde l'état."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def is_file_processed(self, file_id: str, modified_date: str) -> bool:
        """Vérifie si un fichier a déjà été traité."""
        if file_id in self.state['processed_files']:
            last_processed = self.state['processed_files'][file_id]
            return last_processed >= modified_date
        return False
    
    def mark_file_processed(self, file_id: str, modified_date: str):
        """Marque un fichier comme traité."""
        self.state['processed_files'][file_id] = modified_date
        self.save_state()
    
    def detect_deletions(self, current_files: List[str]) -> List[str]:
        """Détecte les fichiers supprimés depuis la dernière sync."""
        previous_files = set(self.state['processed_files'].keys())
        current_files_set = set(current_files)
        
        deleted = list(previous_files - current_files_set)
        
        # Mettre à jour l'état
        for file_id in deleted:
            del self.state['processed_files'][file_id]
            self.state['deleted_files'].append({
                'id': file_id,
                'deletion_date': _dt.datetime.now().isoformat()
            })
        
        self.save_state()
        return deleted


def main() -> None:
    sync()


if __name__ == "__main__":
    main()
