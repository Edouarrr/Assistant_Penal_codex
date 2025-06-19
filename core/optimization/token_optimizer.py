# core/optimization/token_optimizer.py
"""
Module d'optimisation des tokens pour traiter des dossiers pénaux volumineux.
Implémente deux stratégies principales :
1. Résumé hiérarchique (summarization cascade)
2. Chunking intelligent avec priorisation
"""
import tiktoken
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import asyncio
from datetime import datetime
import json
import hashlib

from core.llm.multi_llm_manager import MultiLLMManager
from core.vector_juridique import VectorJuridique


@dataclass
class DocumentChunk:
    """Représente un chunk de document avec métadonnées."""
    content: str
    metadata: Dict[str, Any]
    token_count: int
    relevance_score: float = 0.0
    summary: Optional[str] = None
    chunk_id: str = ""
    
    def __post_init__(self):
        if not self.chunk_id:
            # Générer un ID unique basé sur le contenu
            self.chunk_id = hashlib.md5(self.content.encode()).hexdigest()[:8]


@dataclass
class OptimizationResult:
    """Résultat de l'optimisation."""
    optimized_context: str
    total_tokens: int
    compression_ratio: float
    cost_estimate: float
    strategy_used: str
    chunks_included: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class TokenOptimizer:
    """Optimise l'utilisation des tokens pour les gros dossiers."""
    
    def __init__(self, llm_manager: Optional[MultiLLMManager] = None):
        self.llm_manager = llm_manager or MultiLLMManager()
        self.vector_db = VectorJuridique()
        
        # Encodeur pour compter les tokens
        self.encoder = tiktoken.encoding_for_model("gpt-4")
        
        # Configuration des limites
        self.token_limits = {
            'GPT-4o': 128000,
            'Claude Opus 4': 200000,
            'GPT-3.5': 16000,
            'Mistral': 32000,
            'Gemini': 32000,
            'DeepSeek': 32000,
            'Perplexity': 4000
        }
        
        # Cache des résumés
        self.summary_cache = {}
    
    def count_tokens(self, text: str) -> int:
        """Compte le nombre de tokens dans un texte."""
        return len(self.encoder.encode(text))
    
    async def optimize_for_llm(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        target_model: str,
        strategy: str = "auto",
        max_tokens: Optional[int] = None
    ) -> OptimizationResult:
        """
        Optimise les documents pour un LLM spécifique.
        
        Args:
            documents: Liste des documents à optimiser
            query: Requête de l'utilisateur
            target_model: Modèle LLM cible
            strategy: Stratégie d'optimisation ("hierarchical", "smart_chunking", "auto")
            max_tokens: Limite de tokens (par défaut selon le modèle)
        
        Returns:
            OptimizationResult avec le contexte optimisé
        """
        # Déterminer la limite de tokens
        if max_tokens is None:
            max_tokens = self.token_limits.get(target_model, 8000)
            # Garder de la marge pour la requête et la réponse
            max_tokens = int(max_tokens * 0.7)
        
        # Calculer les tokens actuels
        total_content = "\n\n".join([doc.get('content', '') for doc in documents])
        current_tokens = self.count_tokens(total_content)
        
        # Si ça rentre déjà, pas besoin d'optimiser
        if current_tokens <= max_tokens:
            return OptimizationResult(
                optimized_context=total_content,
                total_tokens=current_tokens,
                compression_ratio=1.0,
                cost_estimate=self._estimate_cost(target_model, current_tokens),
                strategy_used="none",
                chunks_included=len(documents)
            )
        
        # Choisir la stratégie
        if strategy == "auto":
            # Si très gros dossier, utiliser la stratégie hiérarchique
            if current_tokens > max_tokens * 3:
                strategy = "hierarchical"
            else:
                strategy = "smart_chunking"
        
        # Appliquer la stratégie
        if strategy == "hierarchical":
            return await self._hierarchical_summarization(
                documents, query, target_model, max_tokens
            )
        else:
            return await self._smart_chunking(
                documents, query, target_model, max_tokens
            )
    
    async def _hierarchical_summarization(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        target_model: str,
        max_tokens: int
    ) -> OptimizationResult:
        """
        Stratégie 1 : Résumé hiérarchique.
        Crée des résumés de plus en plus condensés jusqu'à respecter la limite.
        """
        start_time = datetime.now()
        
        # Étape 1 : Créer des résumés de niveau 1 (par document)
        level1_summaries = []
        
        for doc in documents:
            # Vérifier le cache
            doc_hash = hashlib.md5(doc.get('content', '').encode()).hexdigest()
            
            if doc_hash in self.summary_cache:
                summary = self.summary_cache[doc_hash]
            else:
                # Générer le résumé
                summary = await self._generate_summary(
                    doc.get('content', ''),
                    level=1,
                    focus=query,
                    max_length=500
                )
                self.summary_cache[doc_hash] = summary
            
            level1_summaries.append({
                'summary': summary,
                'metadata': doc.get('metadata', {}),
                'original_length': len(doc.get('content', ''))
            })
        
        # Étape 2 : Si nécessaire, créer des résumés de niveau 2 (par groupe)
        combined_summaries = self._combine_summaries(level1_summaries, query)
        combined_tokens = self.count_tokens(combined_summaries)
        
        if combined_tokens <= max_tokens:
            # Les résumés de niveau 1 suffisent
            return OptimizationResult(
                optimized_context=combined_summaries,
                total_tokens=combined_tokens,
                compression_ratio=combined_tokens / self.count_tokens("\n\n".join([d.get('content', '') for d in documents])),
                cost_estimate=self._estimate_cost(target_model, combined_tokens),
                strategy_used="hierarchical_level1",
                chunks_included=len(documents),
                metadata={
                    'processing_time': (datetime.now() - start_time).total_seconds(),
                    'summary_levels': 1
                }
            )
        
        # Étape 3 : Résumé de niveau 2 - super condensé
        level2_summary = await self._generate_summary(
            combined_summaries,
            level=2,
            focus=query,
            max_length=max_tokens // 2  # Utiliser la moitié pour le résumé
        )
        
        # Étape 4 : Ajouter les extraits les plus pertinents
        relevant_excerpts = self._extract_relevant_excerpts(
            documents,
            query,
            max_tokens - self.count_tokens(level2_summary)
        )
        
        final_context = f"""## Résumé global du dossier

{level2_summary}

## Extraits pertinents pour votre requête

{relevant_excerpts}"""
        
        final_tokens = self.count_tokens(final_context)
        
        return OptimizationResult(
            optimized_context=final_context,
            total_tokens=final_tokens,
            compression_ratio=final_tokens / self.count_tokens("\n\n".join([d.get('content', '') for d in documents])),
            cost_estimate=self._estimate_cost(target_model, final_tokens),
            strategy_used="hierarchical_level2",
            chunks_included=len(documents),
            metadata={
                'processing_time': (datetime.now() - start_time).total_seconds(),
                'summary_levels': 2,
                'excerpts_included': True
            }
        )
    
    async def _smart_chunking(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        target_model: str,
        max_tokens: int
    ) -> OptimizationResult:
        """
        Stratégie 2 : Chunking intelligent avec priorisation.
        Sélectionne les chunks les plus pertinents selon la requête.
        """
        start_time = datetime.now()
        
        # Étape 1 : Créer des chunks avec métadonnées
        all_chunks = []
        
        for doc in documents:
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            
            # Découper en chunks intelligents
            chunks = self._create_smart_chunks(content, metadata)
            all_chunks.extend(chunks)
        
        # Étape 2 : Calculer la pertinence de chaque chunk
        scored_chunks = await self._score_chunks(all_chunks, query)
        
        # Étape 3 : Sélectionner les meilleurs chunks dans la limite
        selected_chunks = []
        current_tokens = 0
        
        for chunk in sorted(scored_chunks, key=lambda x: x.relevance_score, reverse=True):
            chunk_tokens = chunk.token_count
            
            if current_tokens + chunk_tokens <= max_tokens:
                selected_chunks.append(chunk)
                current_tokens += chunk_tokens
            elif current_tokens + 100 < max_tokens:
                # Essayer de résumer le chunk pour qu'il rentre
                summary = await self._generate_summary(
                    chunk.content,
                    level=1,
                    focus=query,
                    max_length=max_tokens - current_tokens
                )
                if self.count_tokens(summary) + current_tokens <= max_tokens:
                    chunk.content = summary
                    chunk.summary = summary
                    selected_chunks.append(chunk)
                    current_tokens += self.count_tokens(summary)
        
        # Étape 4 : Organiser les chunks sélectionnés
        organized_context = self._organize_chunks(selected_chunks, query)
        
        return OptimizationResult(
            optimized_context=organized_context,
            total_tokens=current_tokens,
            compression_ratio=current_tokens / self.count_tokens("\n\n".join([d.get('content', '') for d in documents])),
            cost_estimate=self._estimate_cost(target_model, current_tokens),
            strategy_used="smart_chunking",
            chunks_included=len(selected_chunks),
            metadata={
                'processing_time': (datetime.now() - start_time).total_seconds(),
                'total_chunks': len(all_chunks),
                'selected_chunks': len(selected_chunks),
                'avg_relevance_score': sum(c.relevance_score for c in selected_chunks) / len(selected_chunks) if selected_chunks else 0
            }
        )
    
    async def _generate_summary(
        self,
        content: str,
        level: int,
        focus: str,
        max_length: int
    ) -> str:
        """Génère un résumé du contenu."""
        # Pour éviter les appels API en développement, utiliser un résumé simple
        if not self.llm_manager:
            # Résumé basique : prendre le début et la fin
            words = content.split()
            if len(words) > max_length // 5:
                start = ' '.join(words[:max_length//10])
                end = ' '.join(words[-max_length//10:])
                return f"{start}... [contenu résumé] ... {end}"
            return content
        
        # Prompt selon le niveau
        if level == 1:
            prompt = f"""Résumez ce document juridique en mettant l'accent sur les éléments pertinents pour la requête suivante : "{focus}"
            
Limitez le résumé à environ {max_length} mots.
Incluez :
- Les faits essentiels
- Les dates importantes
- Les personnes clés
- Les éléments de preuve pertinents

Document :
{content[:5000]}..."""  # Limiter le contenu envoyé
        
        else:  # level 2
            prompt = f"""Créez un résumé exécutif ultra-condensé de ces résumés de documents pour répondre à : "{focus}"

Maximum {max_length} mots.
Focalisez sur :
- Les points critiques pour la requête
- Les contradictions majeures
- Les conclusions essentielles

Résumés :
{content}"""
        
        # Utiliser un modèle rapide pour les résumés
        response = await self.llm_manager.query_multiple(
            prompt=prompt,
            context="",
            selected_models=['GPT-3.5'],  # Modèle rapide et économique
            max_tokens=max_length * 2  # Marge pour les tokens
        )
        
        # Extraire la réponse
        for model, resp in response.get('responses', {}).items():
            if not resp.get('error'):
                return resp.get('content', content[:max_length])
        
        # Fallback
        return content[:max_length * 5]  # Approximation mots -> caractères
    
    def _create_smart_chunks(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """Crée des chunks intelligents basés sur la structure du document."""
        chunks = []
        
        # Stratégie de chunking selon le type de document
        doc_type = metadata.get('type', 'general')
        
        if doc_type in ['audition', 'interrogatoire']:
            # Chunker par question/réponse
            sections = self._split_by_qa(content)
        elif doc_type in ['jugement', 'arrêt']:
            # Chunker par section juridique
            sections = self._split_by_legal_sections(content)
        else:
            # Chunking par paragraphes avec overlap
            sections = self._split_by_paragraphs(content, chunk_size=1000, overlap=200)
        
        for i, section in enumerate(sections):
            chunk = DocumentChunk(
                content=section,
                metadata={
                    **metadata,
                    'chunk_index': i,
                    'chunk_type': doc_type
                },
                token_count=self.count_tokens(section)
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_by_qa(self, content: str) -> List[str]:
        """Découpe un texte en format question/réponse."""
        import re
        
        # Patterns pour détecter les questions/réponses
        patterns = [
            r'(?:Q|QUESTION)\s*[:.].*?(?:R|REPONSE|REP)\s*[:.].*?(?=(?:Q|QUESTION)|$)',
            r'(?:^\d+\.\s*)?(?:Question|Q)\s*:.*?(?:Réponse|R)\s*:.*?(?=(?:^\d+\.|Question|Q)|$)',
        ]
        
        sections = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE | re.MULTILINE)
            if matches:
                sections.extend(matches)
                break
        
        # Fallback : découper par paragraphes
        if not sections:
            sections = content.split('\n\n')
        
        return [s.strip() for s in sections if s.strip()]
    
    def _split_by_legal_sections(self, content: str) -> List[str]:
        """Découpe un document juridique par sections."""
        import re
        
        # Patterns pour les sections juridiques
        section_patterns = [
            r'(?:I+\.|[A-Z]\.|Article\s+\d+|§\s*\d+).*?(?=(?:I+\.|[A-Z]\.|Article\s+\d+|§\s*\d+)|$)',
            r'(?:ATTENDU QUE|CONSIDERANT QUE|PAR CES MOTIFS).*?(?=(?:ATTENDU QUE|CONSIDERANT QUE|PAR CES MOTIFS)|$)',
        ]
        
        sections = []
        for pattern in section_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            if matches:
                sections.extend(matches)
        
        # Si pas de sections trouvées, découper par paragraphes
        if not sections:
            sections = self._split_by_paragraphs(content)
        
        return [s.strip() for s in sections if s.strip()]
    
    def _split_by_paragraphs(
        self,
        content: str,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[str]:
        """Découpe simple par paragraphes avec overlap."""
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            if current_size + para_size > chunk_size and current_chunk:
                # Créer un chunk
                chunks.append('\n\n'.join(current_chunk))
                
                # Garder les derniers paragraphes pour l'overlap
                if overlap > 0:
                    overlap_text = '\n\n'.join(current_chunk[-2:])
                    if len(overlap_text) < overlap:
                        current_chunk = current_chunk[-2:]
                        current_size = len(overlap_text)
                    else:
                        current_chunk = []
                        current_size = 0
                else:
                    current_chunk = []
                    current_size = 0
            
            current_chunk.append(para)
            current_size += para_size
        
        # Dernier chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks
    
    async def _score_chunks(
        self,
        chunks: List[DocumentChunk],
        query: str
    ) -> List[DocumentChunk]:
        """Calcule le score de pertinence de chaque chunk."""
        # Utiliser la recherche vectorielle pour scorer
        query_embedding = await self._get_embedding(query)
        
        for chunk in chunks:
            # Score basé sur plusieurs facteurs
            
            # 1. Similarité sémantique (si embeddings disponibles)
            semantic_score = 0.5  # Default
            
            # 2. Présence de mots-clés
            query_words = set(query.lower().split())
            chunk_words = set(chunk.content.lower().split())
            keyword_score = len(query_words & chunk_words) / len(query_words) if query_words else 0
            
            # 3. Type de document
            doc_type_scores = {
                'audition': 0.9,
                'jugement': 0.8,
                'expertise': 0.7,
                'correspondance': 0.5
            }
            type_score = doc_type_scores.get(chunk.metadata.get('type', ''), 0.5)
            
            # 4. Fraîcheur (documents récents plus pertinents)
            date_score = 0.5
            if 'date' in chunk.metadata:
                try:
                    doc_date = datetime.fromisoformat(chunk.metadata['date'])
                    days_old = (datetime.now() - doc_date).days
                    date_score = max(0.1, 1.0 - (days_old / 365))
                except:
                    pass
            
            # Score final pondéré
            chunk.relevance_score = (
                semantic_score * 0.4 +
                keyword_score * 0.3 +
                type_score * 0.2 +
                date_score * 0.1
            )
        
        return chunks
    
    async def _get_embedding(self, text: str) -> List[float]:
        """Obtient l'embedding d'un texte."""
        # Utiliser OpenAI embeddings si disponible
        try:
            import openai
            response = await openai.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response.data[0].embedding
        except:
            # Fallback : embedding simple basé sur les mots
            words = text.lower().split()
            # Créer un vecteur simple basé sur la fréquence des mots
            return [hash(word) % 1000 / 1000 for word in words[:100]]
    
    def _organize_chunks(
        self,
        chunks: List[DocumentChunk],
        query: str
    ) -> str:
        """Organise les chunks sélectionnés de manière cohérente."""
        # Grouper par type de document
        grouped = {}
        for chunk in chunks:
            doc_type = chunk.metadata.get('type', 'Autre')
            if doc_type not in grouped:
                grouped[doc_type] = []
            grouped[doc_type].append(chunk)
        
        # Construire le contexte organisé
        organized = f"## Contexte pour la requête : {query}\n\n"
        
        # Ordre de priorité des types
        priority_order = [
            'jugement',
            'audition',
            'expertise',
            'rapport',
            'correspondance',
            'autre'
        ]
        
        for doc_type in priority_order:
            if doc_type in grouped:
                organized += f"### {doc_type.capitalize()}s\n\n"
                
                # Trier par score de pertinence
                for chunk in sorted(grouped[doc_type], key=lambda x: x.relevance_score, reverse=True):
                    source = chunk.metadata.get('filename', 'Document')
                    page = chunk.metadata.get('page_number', 'N/A')
                    
                    organized += f"**Source : {source} (Page {page})**\n"
                    organized += f"*Pertinence : {chunk.relevance_score:.0%}*\n\n"
                    
                    # Utiliser le résumé si disponible, sinon le contenu
                    content = chunk.summary if chunk.summary else chunk.content
                    organized += f"{content}\n\n---\n\n"
        
        return organized
    
    def _combine_summaries(
        self,
        summaries: List[Dict[str, Any]],
        query: str
    ) -> str:
        """Combine les résumés de niveau 1 de manière cohérente."""
        combined = f"## Résumé du dossier pour : {query}\n\n"
        
        # Grouper par type si disponible
        by_type = {}
        for summary_data in summaries:
            doc_type = summary_data.get('metadata', {}).get('type', 'general')
            if doc_type not in by_type:
                by_type[doc_type] = []
            by_type[doc_type].append(summary_data)
        
        # Assembler
        for doc_type, items in by_type.items():
            combined += f"### {doc_type.capitalize()}\n\n"
            for item in items:
                combined += item['summary'] + "\n\n"
        
        return combined
    
    def _extract_relevant_excerpts(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        max_tokens: int
    ) -> str:
        """Extrait les passages les plus pertinents des documents."""
        excerpts = []
        query_words = set(query.lower().split())
        
        for doc in documents:
            content = doc.get('content', '')
            # Chercher les paragraphes contenant les mots de la requête
            paragraphs = content.split('\n\n')
            
            for para in paragraphs:
                para_lower = para.lower()
                # Score basé sur le nombre de mots de la requête présents
                score = sum(1 for word in query_words if word in para_lower)
                
                if score > 0:
                    excerpts.append((score, para, doc.get('metadata', {})))
        
        # Trier par score
        excerpts.sort(key=lambda x: x[0], reverse=True)
        
        # Sélectionner les meilleurs dans la limite de tokens
        selected = []
        current_tokens = 0
        
        for score, excerpt, metadata in excerpts:
            excerpt_tokens = self.count_tokens(excerpt)
            if current_tokens + excerpt_tokens <= max_tokens:
                selected.append((excerpt, metadata))
                current_tokens += excerpt_tokens
        
        # Formater
        formatted = ""
        for excerpt, metadata in selected:
            source = metadata.get('filename', 'Document')
            formatted += f"**[{source}]**\n{excerpt}\n\n"
        
        return formatted
    
    def _estimate_cost(self, model: str, tokens: int) -> float:
        """Estime le coût en USD pour un nombre de tokens."""
        # Coûts approximatifs par 1k tokens (input)
        costs = {
            'GPT-4o': 0.005,
            'GPT-3.5': 0.0005,
            'Claude Opus 4': 0.015,
            'Mistral': 0.002,
            'Gemini': 0.00025,
            'DeepSeek': 0.00014,
            'Perplexity': 0.001
        }
        
        cost_per_1k = costs.get(model, 0.001)
        return (tokens / 1000) * cost_per_1k
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques d'optimisation."""
        return {
            'cache_size': len(self.summary_cache),
            'supported_models': list(self.token_limits.keys()),
            'token_limits': self.token_limits,
            'cache_memory_mb': sum(len(s.encode()) for s in self.summary_cache.values()) / 1024 / 1024
        }


# Export
__all__ = ['TokenOptimizer', 'DocumentChunk', 'OptimizationResult']
