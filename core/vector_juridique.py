"""
Module de vectorisation juridique avancée avec ChromaDB.
"""

import os
import json
import logging
import hashlib
from glob import glob
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import re

import yaml
import openai
from openai import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from PyPDF2 import PdfReader
import pandas as pd
from tqdm import tqdm
import numpy as np


class VectorJuridique:
    """Vectorisation juridique avancée pour documents pénaux avec ChromaDB."""

    def __init__(self, settings_path: str = "config/chromadb_settings.yaml") -> None:
        """Initialise le système de vectorisation."""
        self.base_dir = Path(__file__).resolve().parent.parent
        self.settings = self._load_settings(settings_path)
        self._configure_logging()
        
        # Configuration OpenAI
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Configuration des text splitters
        self.text_splitter_lvl1 = RecursiveCharacterTextSplitter(
            chunk_size=self.settings['chunk_size'],
            chunk_overlap=self.settings['chunk_overlap'],
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        
        self.text_splitter_lvl2 = RecursiveCharacterTextSplitter(
            chunk_size=3000,
            chunk_overlap=300,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        
        # Initialisation ChromaDB
        self._init_chromadb()
        
        # Cache pour les embeddings
        self.embedding_cache = {}
        
        # Patterns pour l'extraction d'informations
        self.patterns = {
            'date': r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            'amount': r'\d+(?:\s*\d{3})*(?:[.,]\d+)?\s*(?:€|EUR|euros?)',
            'person': r'(?:M\.|Mme|Me|Dr)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
            'company': r'(?:SARL|SAS|SA|SCI|EURL)\s+[A-Z][A-Z\s]+',
            'case_number': r'\d{2,4}/\d{2,6}',
        }

    @staticmethod
    def _load_settings(path: str) -> Dict:
        """Charge les paramètres depuis le fichier YAML."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("chromadb", {})

    def _configure_logging(self) -> None:
        """Configure le système de logging."""
        log_file = self.base_dir / "logs" / "vectorization.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            filename=str(log_file),
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        self.logger = logging.getLogger(__name__)

    def _init_chromadb(self) -> None:
        """Initialise ChromaDB avec la configuration."""
        persist_dir = Path(self.settings.get("persist_directory", "chroma_db"))
        if not persist_dir.is_absolute():
            persist_dir = self.base_dir / persist_dir
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
        
        # Fonction d'embedding OpenAI
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=self.settings['embedding']['model'],
        )
        
        # Créer ou récupérer la collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.settings['collection_name'],
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )
        
        self.logger.info(f"ChromaDB initialisé avec {self.collection.count()} documents")

    def _extract_metadata(self, file_path: str, page_num: int = None) -> Dict[str, Any]:
        """Extrait les métadonnées d'un fichier."""
        path = Path(file_path)
        
        metadata = {
            "file_name": path.name,
            "file_path": str(path),
            "file_extension": path.suffix.lower(),
            "file_size": path.stat().st_size,
            "creation_date": datetime.fromtimestamp(path.stat().st_ctime).isoformat(),
            "modification_date": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            "vector_date": datetime.now().isoformat(),
            "vector_model": self.settings['embedding']['model'],
        }
        
        if page_num is not None:
            metadata["page_number"] = page_num
        
        # Détection du type de document
        metadata["document_type"] = self._detect_document_type(path.name)
        
        # Extraction d'informations depuis le nom du fichier
        if "PV" in path.name or "audition" in path.name.lower():
            metadata["document_type"] = "audition"
        elif "facture" in path.name.lower():
            metadata["document_type"] = "facture"
        elif "conclusions" in path.name.lower():
            metadata["document_type"] = "conclusions"
        elif "jugement" in path.name.lower() or "arret" in path.name.lower():
            metadata["document_type"] = "decision"
        
        return metadata

    def _detect_document_type(self, filename: str) -> str:
        """Détecte le type de document depuis le nom du fichier."""
        filename_lower = filename.lower()
        
        type_patterns = {
            "audition": ["audition", "pv", "interrogatoire", "garde_vue"],
            "expertise": ["expertise", "expert", "rapport"],
            "financier": ["releve", "bancaire", "virement", "facture", "comptable"],
            "judiciaire": ["jugement", "arret", "ordonnance", "requisitoire"],
            "procedure": ["conclusions", "plainte", "constitution", "memoire"],
            "correspondance": ["lettre", "courrier", "mail", "email"],
            "piece": ["piece", "annexe", "justificatif"],
        }
        
        for doc_type, patterns in type_patterns.items():
            if any(pattern in filename_lower for pattern in patterns):
                return doc_type
        
        return "autre"

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extrait les entités nommées du texte."""
        entities = {
            "dates": [],
            "amounts": [],
            "persons": [],
            "companies": [],
            "case_numbers": [],
        }
        
        # Extraction par patterns regex
        for entity_type, pattern in self.patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if entity_type == 'person':
                entities['persons'] = list(set(matches))
            elif entity_type == 'date':
                entities['dates'] = list(set(matches))
            elif entity_type == 'amount':
                entities['amounts'] = list(set(matches))
            elif entity_type == 'company':
                entities['companies'] = list(set(matches))
            elif entity_type == 'case_number':
                entities['case_numbers'] = list(set(matches))
        
        return entities

    def _summarize(self, text: str, level: int = 1, max_length: int = 500) -> str:
        """Génère un résumé du texte."""
        if len(text) < max_length:
            return text
        
        prompt = f"""Résume ce texte juridique en {max_length} caractères maximum.
Niveau {level} - {'Vue d\'ensemble' if level == 1 else 'Détails importants'}.
Conserve les éléments juridiques clés, dates, montants et noms.

Texte:
{text[:3000]}"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Tu es un assistant juridique expert en résumé de documents pénaux."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_length // 4,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Erreur résumé : {e}")
            return text[:max_length] + "..."

    def _generate_unique_id(self, content: str, metadata: Dict[str, Any]) -> str:
        """Génère un ID unique pour un chunk."""
        hash_input = f"{content}{metadata.get('file_path', '')}{metadata.get('page_number', '')}"
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def process_pdf(self, pdf_path: str, force_reprocess: bool = False) -> Dict[str, Any]:
        """Traite un fichier PDF complet."""
        if not pdf_path.lower().endswith(".pdf"):
            return {"status": "skipped", "reason": "not_pdf"}
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return {"status": "error", "reason": "file_not_found"}
        
        self.logger.info(f"Traitement PDF : {pdf_path}")
        
        stats = {
            "file": str(pdf_path),
            "pages_processed": 0,
            "chunks_created": 0,
            "entities_extracted": {},
            "errors": [],
            "summaries": [],
        }
        
        try:
            # Lire le PDF
            reader = PdfReader(str(pdf_path))
            total_pages = len(reader.pages)
            
            # Traiter chaque page
            for page_num, page in enumerate(tqdm(reader.pages, desc=f"Pages de {pdf_path.name}"), 1):
                try:
                    # Extraire le texte
                    text = page.extract_text()
                    if not text or len(text.strip()) < 50:
                        continue
                    
                    # Métadonnées de base
                    metadata = self._extract_metadata(str(pdf_path), page_num)
                    
                    # Extraction d'entités
                    entities = self._extract_entities(text)
                    metadata["entities"] = json.dumps(entities)
                    
                    # Résumés à deux niveaux
                    summary_lvl1 = self._summarize(text, level=1, max_length=200)
                    summary_lvl2 = self._summarize(text, level=2, max_length=500)
                    
                    metadata["summary_lvl1"] = summary_lvl1
                    metadata["summary_lvl2"] = summary_lvl2
                    
                    # Découpage en chunks
                    chunks = self.text_splitter_lvl1.split_text(text)
                    
                    # Vectoriser et stocker chaque chunk
                    for i, chunk in enumerate(chunks):
                        chunk_metadata = metadata.copy()
                        chunk_metadata["chunk_index"] = i
                        chunk_metadata["total_chunks"] = len(chunks)
                        
                        # ID unique pour le chunk
                        chunk_id = self._generate_unique_id(chunk, chunk_metadata)
                        
                        # Ajouter à ChromaDB
                        self.collection.add(
                            documents=[chunk],
                            metadatas=[chunk_metadata],
                            ids=[chunk_id]
                        )
                        
                        stats["chunks_created"] += 1
                    
                    stats["pages_processed"] += 1
                    
                    # Agrégation des entités
                    for entity_type, entity_list in entities.items():
                        if entity_type not in stats["entities_extracted"]:
                            stats["entities_extracted"][entity_type] = set()
                        stats["entities_extracted"][entity_type].update(entity_list)
                    
                    # Sauvegarder le résumé
                    stats["summaries"].append({
                        "page": page_num,
                        "summary_lvl1": summary_lvl1,
                        "summary_lvl2": summary_lvl2,
                        "entities": entities,
                    })
                    
                except Exception as e:
                    error_msg = f"Erreur page {page_num}: {str(e)}"
                    self.logger.error(error_msg)
                    stats["errors"].append(error_msg)
            
            # Convertir les sets en lists pour la sérialisation
            for entity_type in stats["entities_extracted"]:
                stats["entities_extracted"][entity_type] = list(stats["entities_extracted"][entity_type])
            
            # Sauvegarder les résumés
            self._save_summaries(pdf_path.name, stats["summaries"])
            
            stats["status"] = "success"
            self.logger.info(f"PDF traité : {stats['pages_processed']} pages, {stats['chunks_created']} chunks")
            
        except Exception as e:
            stats["status"] = "error"
            stats["error"] = str(e)
            self.logger.error(f"Erreur traitement PDF {pdf_path}: {e}")
        
        return stats

    def _save_summaries(self, file_name: str, summaries: List[Dict]) -> None:
        """Sauvegarde les résumés dans un fichier JSON."""
        summaries_dir = self.base_dir / "summaries"
        summaries_dir.mkdir(exist_ok=True)
        
        summary_path = summaries_dir / f"{Path(file_name).stem}_summary.json"
        
        summary_data = {
            "file_name": file_name,
            "processing_date": datetime.now().isoformat(),
            "total_pages": len(summaries),
            "summaries": summaries,
        }
        
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)

    def search(
        self, 
        query: str, 
        k: int = 10,
        filter_dict: Dict[str, Any] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """Recherche dans la base vectorielle."""
        try:
            # Paramètres de recherche
            search_kwargs = {
                "query_texts": [query],
                "n_results": k,
            }
            
            # Ajouter les filtres si fournis
            if filter_dict:
                search_kwargs["where"] = filter_dict
            
            # Effectuer la recherche
            results = self.collection.query(**search_kwargs)
            
            # Formater les résultats
            formatted_results = []
            for i in range(len(results['documents'][0])):
                result = {
                    "content": results['documents'][0][i],
                    "score": 1 - results['distances'][0][i],  # Convertir distance en score
                    "id": results['ids'][0][i],
                }
                
                if include_metadata and results.get('metadatas'):
                    result["metadata"] = results['metadatas'][0][i]
                
                formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Erreur recherche : {e}")
            return []

    def search_with_rerank(
        self,
        query: str,
        k: int = 20,
        top_k: int = 10,
        filter_dict: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Recherche avec re-ranking des résultats."""
        # Première recherche élargie
        initial_results = self.search(query, k=k, filter_dict=filter_dict)
        
        if not initial_results:
            return []
        
        # Re-scorer avec un modèle plus puissant
        reranked_results = []
        
        for result in initial_results:
            # Score de pertinence basé sur plusieurs critères
            relevance_score = self._calculate_relevance_score(
                query, 
                result['content'], 
                result.get('metadata', {})
            )
            
            result['rerank_score'] = relevance_score
            reranked_results.append(result)
        
        # Trier par score de reranking
        reranked_results.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        return reranked_results[:top_k]

    def _calculate_relevance_score(
        self, 
        query: str, 
        content: str, 
        metadata: Dict[str, Any]
    ) -> float:
        """Calcule un score de pertinence pour le re-ranking."""
        score = 0.0
        
        # Score basé sur la présence de mots-clés
        query_terms = query.lower().split()
        content_lower = content.lower()
        
        for term in query_terms:
            if term in content_lower:
                score += content_lower.count(term) * 0.1
        
        # Bonus pour certains types de documents
        doc_type = metadata.get('document_type', '')
        if doc_type in ['audition', 'expertise', 'judiciaire']:
            score += 0.2
        
        # Bonus pour les documents récents
        if 'modification_date' in metadata:
            try:
                mod_date = datetime.fromisoformat(metadata['modification_date'])
                days_old = (datetime.now() - mod_date).days
                if days_old < 30:
                    score += 0.3
                elif days_old < 90:
                    score += 0.1
            except:
                pass
        
        return min(score, 1.0)

    def delete_document(self, file_path: str) -> bool:
        """Supprime un document de la base vectorielle."""
        try:
            # Trouver tous les chunks du document
            results = self.collection.get(
                where={"file_path": file_path}
            )
            
            if results['ids']:
                # Supprimer tous les chunks
                self.collection.delete(ids=results['ids'])
                self.logger.info(f"Document supprimé : {file_path} ({len(results['ids'])} chunks)")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erreur suppression : {e}")
            return False

    def update_metadata(self, file_path: str, metadata_updates: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un document."""
        try:
            # Récupérer les chunks du document
            results = self.collection.get(
                where={"file_path": file_path}
            )
            
            if not results['ids']:
                return False
            
            # Mettre à jour chaque chunk
            for i, chunk_id in enumerate(results['ids']):
                current_metadata = results['metadatas'][i]
                current_metadata.update(metadata_updates)
                
                self.collection.update(
                    ids=[chunk_id],
                    metadatas=[current_metadata]
                )
            
            self.logger.info(f"Métadonnées mises à jour : {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur mise à jour métadonnées : {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques de la base vectorielle."""
        try:
            total_docs = self.collection.count()
            
            # Récupérer un échantillon pour les stats
            sample = self.collection.get(limit=1000)
            
            stats = {
                "total_chunks": total_docs,
                "collections": [self.settings['collection_name']],
                "document_types": {},
                "file_extensions": {},
                "recent_documents": [],
                "storage_size_mb": self._get_storage_size(),
            }
            
            # Analyser l'échantillon
            if sample['metadatas']:
                file_paths = set()
                
                for metadata in sample['metadatas']:
                    # Types de documents
                    doc_type = metadata.get('document_type', 'autre')
                    stats['document_types'][doc_type] = stats['document_types'].get(doc_type, 0) + 1
                    
                    # Extensions
                    ext = metadata.get('file_extension', 'unknown')
                    stats['file_extensions'][ext] = stats['file_extensions'].get(ext, 0) + 1
                    
                    # Fichiers uniques
                    if 'file_path' in metadata:
                        file_paths.add(metadata['file_path'])
                
                stats['unique_documents'] = len(file_paths)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Erreur statistiques : {e}")
            return {"error": str(e)}

    def _get_storage_size(self) -> float:
        """Calcule la taille de stockage ChromaDB en MB."""
        try:
            persist_dir = Path(self.settings.get("persist_directory", "chroma_db"))
            if not persist_dir.is_absolute():
                persist_dir = self.base_dir / persist_dir
            
            total_size = 0
            for path in persist_dir.rglob('*'):
                if path.is_file():
                    total_size += path.stat().st_size
            
            return round(total_size / (1024 * 1024), 2)
        except:
            return 0.0

    def export_collection(self, output_path: str) -> bool:
        """Exporte la collection complète."""
        try:
            # Récupérer toutes les données
            all_data = self.collection.get()
            
            export_data = {
                "export_date": datetime.now().isoformat(),
                "collection_name": self.settings['collection_name'],
                "total_documents": len(all_data['ids']),
                "documents": []
            }
            
            # Formater les documents
            for i in range(len(all_data['ids'])):
                doc = {
                    "id": all_data['ids'][i],
                    "content": all_data['documents'][i],
                    "metadata": all_data['metadatas'][i] if all_data.get('metadatas') else {}
                }
                export_data['documents'].append(doc)
            
            # Sauvegarder
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Collection exportée : {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur export : {e}")
            return False

    def backup_collection(self) -> str:
        """Créé une sauvegarde de la collection."""
        if not self.settings.get('maintenance', {}).get('backup_enabled', True):
            return ""
        
        backup_dir = Path(self.settings.get('maintenance', {}).get('backup_directory', 'backups/chromadb'))
        if not backup_dir.is_absolute():
            backup_dir = self.base_dir / backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir / f"chromadb_backup_{timestamp}.json"
        
        if self.export_collection(str(backup_file)):
            return str(backup_file)
        
        return ""

    def cleanup_old_documents(self, max_age_days: int = None) -> int:
        """Nettoie les documents trop anciens."""
        if max_age_days is None:
            max_age_days = self.settings.get('maintenance', {}).get('max_age_days', 365)
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        deleted_count = 0
        
        try:
            # Récupérer tous les documents
            results = self.collection.get()
            
            for i, metadata in enumerate(results.get('metadatas', [])):
                if 'vector_date' in metadata:
                    try:
                        vector_date = datetime.fromisoformat(metadata['vector_date'])
                        if vector_date < cutoff_date:
                            self.collection.delete(ids=[results['ids'][i]])
                            deleted_count += 1
                    except:
                        pass
            
            self.logger.info(f"Nettoyage : {deleted_count} documents supprimés")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Erreur nettoyage : {e}")
            return 0

    def vectorize_directory(
        self, 
        source_dir: str = "ocr_output",
        file_patterns: List[str] = ["*.pdf", "*.txt"],
        recursive: bool = True,
        progress_callback = None
    ) -> Dict[str, Any]:
        """Vectorise tous les fichiers d'un répertoire."""
        source_path = Path(source_dir)
        if not source_path.exists():
            return {"error": "directory_not_found"}
        
        stats = {
            "total_files": 0,
            "processed_files": 0,
            "skipped_files": 0,
            "errors": [],
            "chunks_created": 0,
        }
        
        # Collecter les fichiers
        files_to_process = []
        for pattern in file_patterns:
            if recursive:
                files_to_process.extend(source_path.rglob(pattern))
            else:
                files_to_process.extend(source_path.glob(pattern))
        
        stats["total_files"] = len(files_to_process)
        
        # Traiter chaque fichier
        for i, file_path in enumerate(files_to_process):
            if progress_callback:
                progress_callback(i + 1, stats["total_files"], str(file_path))
            
            try:
                if file_path.suffix.lower() == '.pdf':
                    result = self.process_pdf(str(file_path))
                    if result['status'] == 'success':
                        stats["processed_files"] += 1
                        stats["chunks_created"] += result.get('chunks_created', 0)
                    else:
                        stats["skipped_files"] += 1
                elif file_path.suffix.lower() == '.txt':
                    result = self.process_text_file(str(file_path))
                    if result['status'] == 'success':
                        stats["processed_files"] += 1
                        stats["chunks_created"] += result.get('chunks_created', 0)
                    else:
                        stats["skipped_files"] += 1
                else:
                    stats["skipped_files"] += 1
                    
            except Exception as e:
                error_msg = f"Erreur {file_path}: {str(e)}"
                self.logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        return stats

    def process_text_file(self, file_path: str) -> Dict[str, Any]:
        """Traite un fichier texte."""
        file_path = Path(file_path)
        if not file_path.exists():
            return {"status": "error", "reason": "file_not_found"}
        
        stats = {
            "file": str(file_path),
            "chunks_created": 0,
            "status": "success"
        }
        
        try:
            # Lire le contenu
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if len(text.strip()) < 50:
                return {"status": "skipped", "reason": "too_short"}
            
            # Métadonnées
            metadata = self._extract_metadata(str(file_path))
            
            # Extraction d'entités
            entities = self._extract_entities(text)
            metadata["entities"] = json.dumps(entities)
            
            # Résumés
            metadata["summary_lvl1"] = self._summarize(text, level=1, max_length=200)
            metadata["summary_lvl2"] = self._summarize(text, level=2, max_length=500)
            
            # Découpage en chunks
            chunks = self.text_splitter_lvl1.split_text(text)
            
            # Vectoriser et stocker
            for i, chunk in enumerate(chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk_index"] = i
                chunk_metadata["total_chunks"] = len(chunks)
                
                chunk_id = self._generate_unique_id(chunk, chunk_metadata)
                
                self.collection.add(
                    documents=[chunk],
                    metadatas=[chunk_metadata],
                    ids=[chunk_id]
                )
                
                stats["chunks_created"] += 1
            
            self.logger.info(f"Fichier texte traité : {file_path.name} ({stats['chunks_created']} chunks)")
            
        except Exception as e:
            stats["status"] = "error"
            stats["error"] = str(e)
            self.logger.error(f"Erreur traitement texte {file_path}: {e}")
        
        return stats


def main() -> None:
    """Point d'entrée pour le traitement en ligne de commande."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vectorisation juridique avec ChromaDB")
    parser.add_argument("--source", default="ocr_output", help="Répertoire source")
    parser.add_argument("--recursive", action="store_true", help="Parcours récursif")
    parser.add_argument("--stats", action="store_true", help="Afficher les statistiques")
    parser.add_argument("--backup", action="store_true", help="Créer une sauvegarde")
    parser.add_argument("--cleanup", type=int, help="Nettoyer les documents de plus de X jours")
    
    args = parser.parse_args()
    
    vect = VectorJuridique()
    
    if args.stats:
        stats = vect.get_statistics()
        print(json.dumps(stats, indent=2))
    elif args.backup:
        backup_path = vect.backup_collection()
        print(f"Sauvegarde créée : {backup_path}")
    elif args.cleanup:
        deleted = vect.cleanup_old_documents(args.cleanup)
        print(f"Documents supprimés : {deleted}")
    else:
        print(f"Vectorisation du répertoire : {args.source}")
        stats = vect.vectorize_directory(
            args.source, 
            recursive=args.recursive,
            progress_callback=lambda i, t, f: print(f"[{i}/{t}] {f}")
        )
        print(f"\nRésultats :")
        print(f"- Fichiers traités : {stats['processed_files']}")
        print(f"- Fichiers ignorés : {stats['skipped_files']}")
        print(f"- Chunks créés : {stats['chunks_created']}")
        if stats['errors']:
            print(f"- Erreurs : {len(stats['errors'])}")


if __name__ == "__main__":
    main()
