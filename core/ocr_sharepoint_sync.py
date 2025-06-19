"""Synchronize documents from SharePoint and perform OCR.

This module connects to Microsoft SharePoint via the Graph API, downloads new or
modified files, sanitizes filenames, and performs OCR using Google Vision. OCR
results are stored in ``ocr_output/`` mirroring the ``raw_documents/``
structure.

Usage::

    python -m core.ocr_sharepoint_sync
"""

from __future__ import annotations

import datetime as _dt
import io
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import msal
import requests
from google.api_core.exceptions import GoogleAPIError
from google.cloud import vision
from pdf2image import convert_from_path

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
    """Return a filesystem-friendly path segment."""

    normalized = unicodedata.normalize("NFD", segment)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^A-Za-z0-9_.-]", "", normalized)
    return normalized[:100]


def _sanitize_path(path: Path) -> Path:
    return Path(*(_normalize_segment(p) for p in path.parts))


class GraphClient:
    """Simple Microsoft Graph API client for SharePoint."""

    def __init__(self) -> None:
        self.tenant_id = os.environ.get("MS_TENANT_ID", "")
        self.client_id = os.environ.get("MS_CLIENT_ID", "")
        self.client_secret = os.environ.get("MS_CLIENT_SECRET", "")
        self.site_id = os.environ.get("SHAREPOINT_SITE_ID", "")
        self.drive_id = os.environ.get("SHAREPOINT_DOC_LIB", "")
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self._app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret,
        )
        self._base = "https://graph.microsoft.com/v1.0"

    def _token(self) -> str:
        scope = ["https://graph.microsoft.com/.default"]
        result = self._app.acquire_token_for_client(scopes=scope)
        if "access_token" not in result:
            raise RuntimeError(
                f"Token acquisition failed: {result.get('error_description')}"
            )
        return str(result["access_token"])

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}"}

    def walk(
        self, item_id: str = "root", prefix: Path | None = None
    ) -> Iterable[Tuple[Dict, Path]]:
        """Yield ``(item, relative_path)`` tuples for all files in the drive."""

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


def _needs_download(item: Dict, local_path: Path) -> bool:
    if not local_path.exists():
        return True
    remote_time = _dt.datetime.fromisoformat(
        item["lastModifiedDateTime"].rstrip("Z")
    )
    local_time = _dt.datetime.fromtimestamp(local_path.stat().st_mtime)
    return remote_time > local_time


def _needs_ocr(local_path: Path) -> bool:
    out = OCR_DIR / local_path.relative_to(RAW_DIR).with_suffix(".txt")
    if not out.exists():
        return True
    return out.stat().st_mtime < local_path.stat().st_mtime


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
                    image_context={
                        "language_hints": ["fr", "en"],
                        "enable_auto_rotation": True,
                    },
                )
                if resp.error.message:
                    raise RuntimeError(resp.error.message)
            except GoogleAPIError:
                resp = client.text_detection(image=image)
                if resp.error.message:
                    raise RuntimeError(resp.error.message)
            texts.append(resp.full_text_annotation.text or "")
            table = _extract_tables(resp)
            if table:
                texts.append(table)
    else:
        with open(path, "rb") as fh:
            content = fh.read()
        image = vision.Image(content=content)
        try:
            resp = client.document_text_detection(
                image=image,
                image_context={
                    "language_hints": ["fr", "en"],
                    "enable_auto_rotation": True,
                },
            )
            if resp.error.message:
                raise RuntimeError(resp.error.message)
        except GoogleAPIError:
            resp = client.text_detection(image=image)
            if resp.error.message:
                raise RuntimeError(resp.error.message)
        texts.append(resp.full_text_annotation.text or "")
        table = _extract_tables(resp)
        if table:
            texts.append(table)
    return "\n\n".join(texts)


def _extract_tables(resp: vision.AnnotateImageResponse) -> str:
    """Return TSV text from TABLE blocks in an annotation."""

    if not resp.full_text_annotation.pages:
        return ""
    tables: List[str] = []
    for page in resp.full_text_annotation.pages:
        for block in page.blocks:
            if block.block_type == vision.Block.BlockType.TABLE:
                rows = []
                for par in block.paragraphs:
                    words: List[str] = []
                    for word in par.words:
                        words.append("".join(sym.text for sym in word.symbols))
                    rows.append("\t".join(words))
                tables.append("\n".join(rows))
    return "\n\n".join(tables)


def sync() -> None:
    """Synchronize SharePoint files and run OCR where needed."""

    _setup_logging()
    client = GraphClient()

    for item, rel in client.walk():
        sanitized_rel = _sanitize_path(rel)
        local = RAW_DIR / sanitized_rel
        if _needs_download(item, local):
            try:
                client.download(item, local)
            except Exception as exc:  # pragma: no cover - network interactions
                _log_error(local, "download failed", exc)
                continue
        if _needs_ocr(local):
            try:
                text = _ocr_file(local)
                out = OCR_DIR / sanitized_rel.with_suffix(".txt")
                out.parent.mkdir(parents=True, exist_ok=True)
                with open(out, "w", encoding="utf-8") as fh:
                    fh.write(text)
            except Exception as exc:  # pragma: no cover - network interactions
                _log_error(local, "ocr failed", exc)


def main() -> None:
    sync()


if __name__ == "__main__":
    main()

