# core/optimization/context_manager.py
"""
Gestionnaire de contexte avec cache pour optimiser la réutilisation des tokens.
Système 2 d'optimisation : évite de re-tokenizer les mêmes documents.
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pickle
import asyncio
from dataclasses import dataclass, field

import streamlit as st
from core.optimization.token_optimizer import TokenOptimizer, OptimizationResult


@dataclass
class CachedContext:
    """Représente un contexte mis en cache."""
    context_id: str
    query: str
    documents_hash: str
    optimized_context: str
    token_count: int
    model: str
    strategy: str
    created_at: datetime
    last_used: datetime
    usage_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self, ttl_hours: int = 24) -> bool:
        """Vérifie si le cache est encore valide."""
        age = datetime.now() - self.created_at
        return age < timedelta(hours=ttl_hours)


class ContextManager:
    """
    Gère les contextes optimisés avec mise en cache intelligente.
    Évite de retraiter les mêmes documents pour des requêtes similaires.
    """
    
    def __init__(self, cache_dir: str = "data/context_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.token_optimizer = TokenOptimizer()
        
        # Cache en mémoire pour la session
        self.memory_cache: Dict[str, CachedContext] = {}
        
        # Charger le cache persistant
        self.persistent_cache = self._load_persistent_cache()
        
        # Configuration
        self.config = {
            'cache_ttl_hours': 24,
            'max_cache_size_mb': 100,
            'similarity_threshold': 0.85,
            'max_memory_cache': 50
        }
        
        # Statistiques
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'tokens_saved': 0,
            'time_saved_seconds': 0
        }
    
    async def get_optimized_context(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        model: str,
        strategy: str = "auto",
        force_refresh: bool = False
    ) -> Tuple[OptimizationResult, bool]:
        """
        Obtient un contexte optimisé, depuis le cache si possible.
        
        Returns:
            (OptimizationResult, from_cache: bool)
        """
        # Générer l'identifiant unique pour cette combinaison
        context_id = self._generate_context_id(documents, query, model, strategy)
        
        # Vérifier le cache si pas de refresh forcé
        if not force_refresh:
            cached = self._get_from_cache(context_id)
            if cached:
                self.stats['cache_hits'] += 1
                self.stats['tokens_saved'] += cached.token_count
                
                # Mettre à jour l'usage
                cached.last_used = datetime.now()
                cached.usage_count += 1
                
                # Retourner le résultat depuis le cache
                result = OptimizationResult(
                    optimized_context=cached.optimized_context,
                    total_tokens=cached.token_count,
                    compression_ratio=cached.metadata.get('compression_ratio', 1.0),
                    cost_estimate=cached.metadata.get('cost_estimate', 0),
                    strategy_used=cached.strategy,
                    chunks_included=cached.metadata.get('chunks_included', 0),
                    metadata={
                        **cached.metadata,
                        'from_cache': True,
                        'cache_age_hours': (datetime.now() - cached.created_at).total_seconds() / 3600
                    }
                )
                
                return result, True
        
        # Pas en cache ou refresh forcé - optimiser
        self.stats['cache_misses'] += 1
        start_time = datetime.now()
        
        # Vérifier si on a une requête similaire en cache
        similar_context = self._find_similar_context(query, model, documents)
        if similar_context and not force_refresh:
            # Adapter le contexte similaire
            adapted_result = await self._adapt_similar_context(
                similar_context, query, documents
            )
            if adapted_result:
                return adapted_result, True
        
        # Optimisation complète nécessaire
        result = await self.token_optimizer.optimize_for_llm(
            documents=documents,
            query=query,
            target_model=model,
            strategy=strategy
        )
        
        # Calculer le temps économisé pour les futures utilisations
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Mettre en cache
        cached_context = CachedContext(
            context_id=context_id,
            query=query,
            documents_hash=self._hash_documents(documents),
            optimized_context=result.optimized_context,
            token_count=result.total_tokens,
            model=model,
            strategy=result.strategy_used,
            created_at=datetime.now(),
            last_used=datetime.now(),
            metadata={
                **result.metadata,
                'compression_ratio': result.compression_ratio,
                'cost_estimate': result.cost_estimate,
                'chunks_included': result.chunks_included,
                'processing_time': processing_time
            }
        )
        
        self._add_to_cache(cached_context)
        
        return result, False
    
    def _generate_context_id(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        model: str,
        strategy: str
    ) -> str:
        """Génère un ID unique pour un contexte."""
        # Combiner tous les éléments
        elements = [
            self._hash_documents(documents),
            query.lower().strip(),
            model,
            strategy
        ]
        
        combined = "|".join(elements)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _hash_documents(self, documents: List[Dict[str, Any]]) -> str:
        """Génère un hash pour un ensemble de documents."""
        # Extraire le contenu essentiel
        contents = []
        for doc in sorted(documents, key=lambda x: x.get('metadata', {}).get('filename', '')):
            content = doc.get('content', '')[:1000]  # Premiers 1000 chars
            metadata = doc.get('metadata', {})
            doc_id = metadata.get('id', '') or metadata.get('filename', '')
            contents.append(f"{doc_id}:{content}")
        
        combined = "\n".join(contents)
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _get_from_cache(self, context_id: str) -> Optional[CachedContext]:
        """Récupère un contexte depuis le cache."""
        # Vérifier le cache mémoire d'abord
        if context_id in self.memory_cache:
            cached = self.memory_cache[context_id]
            if cached.is_valid(self.config['cache_ttl_hours']):
                return cached
            else:
                # Invalide, supprimer
                del self.memory_cache[context_id]
        
        # Vérifier le cache persistant
        if context_id in self.persistent_cache:
            cached = self.persistent_cache[context_id]
            if cached.is_valid(self.config['cache_ttl_hours']):
                # Ramener en mémoire
                self.memory_cache[context_id] = cached
                return cached
            else:
                # Invalide, supprimer
                del self.persistent_cache[context_id]
        
        return None
    
    def _find_similar_context(
        self,
        query: str,
        model: str,
        documents: List[Dict[str, Any]]
    ) -> Optional[CachedContext]:
        """
        Trouve un contexte similaire qui pourrait être adapté.
        Utilise la similarité sémantique des requêtes.
        """
        # Calculer le hash des documents
        docs_hash = self._hash_documents(documents)
        
        # Chercher dans tous les caches
        all_cached = {**self.memory_cache, **self.persistent_cache}
        
        candidates = []
        for cached in all_cached.values():
            # Même modèle et mêmes documents
            if cached.model == model and cached.documents_hash == docs_hash:
                # Calculer la similarité des requêtes
                similarity = self._calculate_query_similarity(query, cached.query)
                
                if similarity >= self.config['similarity_threshold']:
                    candidates.append((similarity, cached))
        
        # Retourner le plus similaire
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        
        return None
    
    def _calculate_query_similarity(self, query1: str, query2: str) -> float:
        """Calcule la similarité entre deux requêtes."""
        # Simplification : similarité basée sur les mots communs
        # En production, utiliser des embeddings
        
        words1 = set(query1.lower().split())
        words2 = set(query2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        # Jaccard similarity
        jaccard = len(intersection) / len(union)
        
        # Bonus si les mots importants sont communs
        important_words = {'plainte', 'conclusions', 'analyse', 'contradiction', 'chronologie'}
        important_common = (words1 & words2) & important_words
        
        bonus = len(important_common) * 0.1
        
        return min(1.0, jaccard + bonus)
    
    async def _adapt_similar_context(
        self,
        similar_context: CachedContext,
        new_query: str,
        documents: List[Dict[str, Any]]
    ) -> Optional[Tuple[OptimizationResult, bool]]:
        """Adapte un contexte similaire pour une nouvelle requête."""
        # Si la requête est très proche, réutiliser tel quel
        similarity = self._calculate_query_similarity(new_query, similar_context.query)
        
        if similarity >= 0.95:
            # Quasi-identique, réutiliser
            result = OptimizationResult(
                optimized_context=similar_context.optimized_context,
                total_tokens=similar_context.token_count,
                compression_ratio=similar_context.metadata.get('compression_ratio', 1.0),
                cost_estimate=similar_context.metadata.get('cost_estimate', 0),
                strategy_used=similar_context.strategy,
                chunks_included=similar_context.metadata.get('chunks_included', 0),
                metadata={
                    **similar_context.metadata,
                    'from_cache': True,
                    'adapted': False,
                    'original_query': similar_context.query
                }
            )
            return result, True
        
        # Sinon, adapter légèrement le contexte
        # Ajouter une note sur la nouvelle requête
        adapted_context = f"""## Contexte adapté pour : {new_query}
*Basé sur une analyse similaire pour : "{similar_context.query}"*

{similar_context.optimized_context}

### Focus spécifique pour votre nouvelle requête
Veuillez porter une attention particulière aux éléments liés à : {new_query}"""
        
        new_tokens = self.token_optimizer.count_tokens(adapted_context)
        
        result = OptimizationResult(
            optimized_context=adapted_context,
            total_tokens=new_tokens,
            compression_ratio=similar_context.metadata.get('compression_ratio', 1.0),
            cost_estimate=similar_context.metadata.get('cost_estimate', 0) * 1.1,  # Légère augmentation
            strategy_used=f"{similar_context.strategy}_adapted",
            chunks_included=similar_context.metadata.get('chunks_included', 0),
            metadata={
                **similar_context.metadata,
                'from_cache': True,
                'adapted': True,
                'original_query': similar_context.query,
                'similarity_score': similarity
            }
        )
        
        return result, True
    
    def _add_to_cache(self, cached_context: CachedContext):
        """Ajoute un contexte au cache."""
        # Ajouter au cache mémoire
        if len(self.memory_cache) >= self.config['max_memory_cache']:
            # Supprimer le plus ancien/moins utilisé
            oldest = min(
                self.memory_cache.values(),
                key=lambda x: (x.usage_count, x.last_used)
            )
            del self.memory_cache[oldest.context_id]
        
        self.memory_cache[cached_context.context_id] = cached_context
        
        # Ajouter au cache persistant
        self.persistent_cache[cached_context.context_id] = cached_context
        self._save_persistent_cache()
    
    def _load_persistent_cache(self) -> Dict[str, CachedContext]:
        """Charge le cache persistant depuis le disque."""
        cache_file = self.cache_dir / "context_cache.pkl"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Erreur chargement cache : {e}")
                return {}
        
        return {}
    
    def _save_persistent_cache(self):
        """Sauvegarde le cache persistant sur disque."""
        cache_file = self.cache_dir / "context_cache.pkl"
        
        # Vérifier la taille du cache
        if self._get_cache_size_mb() > self.config['max_cache_size_mb']:
            self._cleanup_cache()
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(self.persistent_cache, f)
        except Exception as e:
            print(f"Erreur sauvegarde cache : {e}")
    
    def _get_cache_size_mb(self) -> float:
        """Calcule la taille du cache en MB."""
        total_size = 0
        for cached in self.persistent_cache.values():
            # Estimation approximative
            total_size += len(cached.optimized_context.encode())
            total_size += len(json.dumps(cached.metadata).encode())
        
        return total_size / 1024 / 1024
    
    def _cleanup_cache(self):
        """Nettoie le cache en supprimant les entrées expirées ou peu utilisées."""
        # Supprimer les expirés
        expired = []
        for context_id, cached in self.persistent_cache.items():
            if not cached.is_valid(self.config['cache_ttl_hours']):
                expired.append(context_id)
        
        for context_id in expired:
            del self.persistent_cache[context_id]
        
        # Si encore trop gros, supprimer les moins utilisés
        if self._get_cache_size_mb() > self.config['max_cache_size_mb']:
            # Trier par utilisation
            sorted_cache = sorted(
                self.persistent_cache.items(),
                key=lambda x: (x[1].usage_count, x[1].last_used)
            )
            
            # Supprimer la moitié la moins utilisée
            to_remove = len(sorted_cache) // 2
            for context_id, _ in sorted_cache[:to_remove]:
                del self.persistent_cache[context_id]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache."""
        total_cached = len(self.memory_cache) + len(self.persistent_cache)
        
        # Calculer les économies
        total_tokens_saved = self.stats['tokens_saved']
        
        # Estimation du coût économisé (basé sur GPT-4)
        cost_saved = (total_tokens_saved / 1000) * 0.005
        
        # Temps économisé
        time_saved = sum(
            c.metadata.get('processing_time', 0) * (c.usage_count - 1)
            for c in self.persistent_cache.values()
        )
        
        return {
            'total_cached_contexts': total_cached,
            'memory_cache_size': len(self.memory_cache),
            'persistent_cache_size': len(self.persistent_cache),
            'cache_size_mb': self._get_cache_size_mb(),
            'cache_hit_rate': (
                self.stats['cache_hits'] / 
                (self.stats['cache_hits'] + self.stats['cache_misses'])
                if (self.stats['cache_hits'] + self.stats['cache_misses']) > 0
                else 0
            ),
            'tokens_saved': total_tokens_saved,
            'cost_saved_usd': cost_saved,
            'time_saved_seconds': time_saved,
            'stats': self.stats
        }
    
    def display_cache_dashboard(self):
        """Affiche un dashboard Streamlit des statistiques du cache."""
        stats = self.get_cache_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Cache Hit Rate",
                f"{stats['cache_hit_rate']:.1%}",
                help="Pourcentage de requêtes servies depuis le cache"
            )
        
        with col2:
            st.metric(
                "Tokens économisés",
                f"{stats['tokens_saved']:,}",
                help="Nombre total de tokens non recalculés"
            )
        
        with col3:
            st.metric(
                "Coût économisé",
                f"${stats['cost_saved_usd']:.2f}",
                help="Économies estimées en USD"
            )
        
        with col4:
            time_saved_min = stats['time_saved_seconds'] / 60
            st.metric(
                "Temps gagné",
                f"{time_saved_min:.0f} min",
                help="Temps de traitement économisé"
            )
        
        # Graphique d'utilisation du cache
        if st.checkbox("Voir les détails du cache"):
            st.write(f"**Contextes en cache** : {stats['total_cached_contexts']}")
            st.write(f"**Taille du cache** : {stats['cache_size_mb']:.1f} MB")
            
            # Top des requêtes en cache
            if self.persistent_cache:
                st.write("**Top 5 des contextes les plus réutilisés :**")
                
                top_contexts = sorted(
                    self.persistent_cache.values(),
                    key=lambda x: x.usage_count,
                    reverse=True
                )[:5]
                
                for i, ctx in enumerate(top_contexts, 1):
                    st.write(
                        f"{i}. `{ctx.query[:50]}...` "
                        f"(utilisé {ctx.usage_count} fois, "
                        f"économisé {ctx.token_count * (ctx.usage_count - 1):,} tokens)"
                    )


# Singleton pour l'application
_context_manager = None

def get_context_manager() -> ContextManager:
    """Retourne l'instance singleton du gestionnaire de contexte."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager


# Export
__all__ = ['ContextManager', 'CachedContext', 'get_context_manager']
