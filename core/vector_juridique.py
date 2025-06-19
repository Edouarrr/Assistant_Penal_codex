"""
Module de vectorisation juridique avancée.
"""

import os
import json
import logging
from glob import glob
from pathlib import Path
from typing import List, Dict

import yaml
import openai
from langchain.text_splitter import RecursiveCharacterTextSplitter
from chromadb import PersistentClient
from chromadb.utils import embedding_functions
from PyPDF2 import PdfReader


class VectorJuridique:
    """Vectorisation juridique avancée pour documents pénaux."""

    def __init__(self, settings_path: str = "config/vector_settings.yaml") -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.settings = self._load_settings(settings_path)
        self._configure_logging(self.settings.get("log_path"))
        openai.api_key = os.getenv("OPENAI_API_KEY")

        self.text_splitter_lvl1 = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.get("chunk_size", 800),
            chunk_overlap=self.settings.get("chunk_overlap", 100),
        )
        self.text_splitter_lvl2 = RecursiveCharacterTextSplitter(
            chunk_size=3000,
            chunk_overlap=self.settings.get("chunk_overlap", 100),
        )

        persist_dir = Path(self.settings.get("persist_directory", "chroma_db"))
        if not persist_dir.is_absolute():
            persist_dir = self.base_dir / persist_dir
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(
            "legal_vectors",
            embedding_function=embedding_functions.OpenAIEmbeddingFunction(
                api_key=openai.api_key,
                model_name=self.settings.get("model", "text-embedding-ada-002"),
            ),
        )

    @staticmethod
    def _load_settings(path: str) -> Dict:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("vectorization", {})

    def _configure_logging(self, log_path: str) -> None:
        log_file = Path(log_path)
        if not log_file.is_absolute():
            log_file = self.base_dir / log_file
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_file),
            level=logging.ERROR,
            format="%(asctime)s %(levelname)s:%(message)s",
        )

    def _summarize(self, text: str, level: int) -> str:
        prompt = f"Résume niveau {level} du texte suivant :\n{text}"
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logging.error(f"OpenAI summarization failed: {exc}")
            return ""

    def _read_pdf_pages(self, pdf_path: str) -> List[str]:
        reader = PdfReader(pdf_path)
        return [page.extract_text() or "" for page in reader.pages]

    def process_pdf(self, pdf_path: str) -> None:
        file_name = os.path.basename(pdf_path)
        pages = self._read_pdf_pages(pdf_path)
        summaries_lvl2 = []

        for page_number, page_text in enumerate(pages, start=1):
            if not page_text.strip():
                continue
            page_summary = self._summarize(page_text, level=2)
            summaries_lvl2.append({"page": page_number, "summary_lvl2": page_summary})

            chunks = self.text_splitter_lvl1.split_text(page_text)
            for chunk in chunks:
                summary_lvl1 = self._summarize(chunk, level=1)
                metadata = {
                    "file_name": file_name,
                    "page_number": page_number,
                    "summary_lvl1": summary_lvl1,
                    "summary_lvl2": page_summary,
                    "embedding_model": self.settings.get("model"),
                }
                try:
                    self.collection.add(documents=[chunk], metadatas=[metadata])
                except Exception as exc:
                    logging.error(f"Error adding chunk to Chroma: {exc}")

        self._save_summaries(file_name, summaries_lvl2)

    def _save_summaries(self, file_name: str, summaries: List[Dict]) -> None:
        summaries_dir = Path("summaries")
        summaries_dir.mkdir(exist_ok=True)
        summary_path = summaries_dir / f"{Path(file_name).stem}_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)

    def vectorize_directory(self, source_dir: str = "ocr_output") -> None:
        pattern = os.path.join(source_dir, "**", "*.pdf")
        for pdf_file in glob(pattern, recursive=True):
            try:
                self.process_pdf(pdf_file)
            except Exception as exc:
                logging.error(f"Failed to process {pdf_file}: {exc}")


def main() -> None:
    vect = VectorJuridique()
    vect.vectorize_directory("ocr_output")


if __name__ == "__main__":
    main()
