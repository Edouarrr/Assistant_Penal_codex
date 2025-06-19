"""
Module de recherche intelligente avec support @mentions et dialogue interactif.
"""
import re
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

import streamlit as st
from core.vector_juridique import VectorJuridique
from core.llm.multi_llm_manager import MultiLLMManager
from core.search.dialogue_manager import DialogueManager


@dataclass
class SearchQuery:
    """Représente une requête de recherche parsée."""
    raw_query: str
    clean_query: str
    mentions: List[Dict[str, str]] = field(default_factory=list)  # {'type': 'dossier/fichier', 'name': '...'}
    filters: Dict[str, Any] = field(default_factory=dict)
    intent: str = ""  # redaction, analyse, recherche, etc.
    models: List[str] = field(default_factory=list)


class IntelligentSearch:
    """Système de recherche intelligent avec parsing avancé."""
    
    def __init__(self):
        self.vector_db = VectorJuridique()
        self.llm_manager = MultiLLMManager()
        self.dialogue_manager = DialogueManager()
        
        # Patterns pour parser la requête
        self.patterns = {
            'mention': r'@(\w+)',
            'dossier': r'@dossier[:\s]*([^\s,]+)',
            'fichier': r'@fichier[:\s]*([^\s,]+)',
            'date': r'depuis\s+(\d+)\s+(jours?|mois|semaines?)',
            'auteur': r'auteur[:\s]*([^\s,]+)',
            'type': r'type[:\s]*([^\s,]+)',
        }
        
        # Mots-clés d'intention
        self.intent_keywords = {
            'redaction': ['rédige', 'écris', 'prépare', 'draft', 'formule'],
            'analyse': ['analyse', 'examine', 'étudie', 'vérifie', 'contrôle', 'détecte'],
            'recherche': ['trouve', 'cherche', 'recherche', 'localise', 'identifie'],
            'extraction': ['extrais', 'liste', 'énumère', 'compile'],
            'comparaison': ['compare', 'confronte', 'oppose'],
            'synthese': ['résume', 'synthétise', 'récapitule'],
        }
        
        # Cache des dossiers/fichiers pour l'autocomplétion
        self._build_file_cache()
    
    def _build_file_cache(self):
        """Construit le cache des fichiers pour l'autocomplétion."""
        self.file_cache = {
            'dossiers': set(),
            'fichiers': set(),
            'all_names': set()
        }
        
        try:
            # Récupérer les fichiers depuis la base vectorielle
            stats = self.vector_db.get_statistics()
            
            # Simuler quelques entrées pour la démo
            # En production, cela viendrait de la vraie base
            self.file_cache['dossiers'] = {
                'martin', 'dupont', 'corruption_mairie', 
                'blanchiment_2024', 'escroquerie_bancaire'
            }
            
            self.file_cache['fichiers'] = {
                'pv_audition_martin', 'rapport_expert_comptable',
                'conclusions_adverses', 'plainte_initiale'
            }
            
            self.file_cache['all_names'] = (
                self.file_cache['dossiers'] | self.file_cache['fichiers']
            )
            
        except Exception as e:
            st.error(f"Erreur construction cache : {e}")
    
    def parse_query(self, raw_query: str) -> SearchQuery:
        """Parse une requête et extrait les mentions, filtres et intention."""
        query = SearchQuery(raw_query=raw_query, clean_query=raw_query)
        
        # Extraire les @mentions
        mentions = re.findall(self.patterns['mention'], raw_query)
        for mention in mentions:
            mention_lower = mention.lower()
            
            # Déterminer le type de mention
            if mention_lower in self.file_cache['dossiers']:
                query.mentions.append({'type': 'dossier', 'name': mention})
            elif mention_lower in self.file_cache['fichiers']:
                query.mentions.append({'type': 'fichier', 'name': mention})
            else:
                # Recherche floue
                closest = self._find_closest_match(mention_lower)
                if closest:
                    query.mentions.append(closest)
        
        # Nettoyer la requête des mentions
        clean_query = raw_query
        for pattern in ['@dossier[:\s]*[^\s,]+', '@fichier[:\s]*[^\s,]+', '@\w+']:
            clean_query = re.sub(pattern, '', clean_query)
        query.clean_query = clean_query.strip()
        
        # Extraire les filtres
        # Filtre par date
        date_match = re.search(self.patterns['date'], raw_query)
        if date_match:
            quantity = int(date_match.group(1))
            unit = date_match.group(2)
            query.filters['date'] = {'quantity': quantity, 'unit': unit}
        
        # Filtre par auteur
        author_match = re.search(self.patterns['auteur'], raw_query)
        if author_match:
            query.filters['author'] = author_match.group(1)
        
        # Filtre par type
        type_match = re.search(self.patterns['type'], raw_query)
        if type_match:
            query.filters['document_type'] = type_match.group(1)
        
        # Détecter l'intention
        query.intent = self._detect_intent(clean_query)
        
        # Extraire les modèles demandés
        query.models = self._extract_requested_models(raw_query)
        
        return query
    
    def _find_closest_match(self, mention: str) -> Optional[Dict[str, str]]:
        """Trouve la correspondance la plus proche pour une mention."""
        # Recherche par préfixe
        for name in self.file_cache['all_names']:
            if name.startswith(mention) or mention in name:
                if name in self.file_cache['dossiers']:
                    return {'type': 'dossier', 'name': name}
                else:
                    return {'type': 'fichier', 'name': name}
        
        # Recherche floue (simplifiée)
        from difflib import get_close_matches
        matches = get_close_matches(mention, self.file_cache['all_names'], n=1, cutoff=0.6)
        if matches:
            name = matches[0]
            if name in self.file_cache['dossiers']:
                return {'type': 'dossier', 'name': name}
            else:
                return {'type': 'fichier', 'name': name}
        
        return None
    
    def _detect_intent(self, query: str) -> str:
        """Détecte l'intention principale de la requête."""
        query_lower = query.lower()
        
        for intent, keywords in self.intent_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return intent
        
        return 'recherche'  # Par défaut
    
    def _extract_requested_models(self, query: str) -> List[str]:
        """Extrait les modèles LLM explicitement demandés."""
        models = []
        query_lower = query.lower()
        
        model_mapping = {
            'gpt4': 'GPT-4o',
            'gpt-4': 'GPT-4o',
            'gpt3': 'GPT-3.5',
            'gpt-3': 'GPT-3.5',
            'claude': 'Claude Opus 4',
            'opus': 'Claude Opus 4',
            'perplexity': 'Perplexity',
            'mistral': 'Mistral',
            'gemini': 'Gemini',
            'deepseek': 'DeepSeek',
        }
        
        for keyword, model_name in model_mapping.items():
            if keyword in query_lower:
                models.append(model_name)
        
        # Si aucun modèle spécifié, utiliser les défauts
        if not models:
            models = ['GPT-4o', 'Claude Opus 4']
        
        return models
    
    def build_search_filters(self, parsed_query: SearchQuery) -> Dict[str, Any]:
        """Construit les filtres ChromaDB depuis la requête parsée."""
        filters = {}
        
        # Filtres par mention
        if parsed_query.mentions:
            file_paths = []
            for mention in parsed_query.mentions:
                if mention['type'] == 'dossier':
                    # Rechercher tous les fichiers du dossier
                    filters['$or'] = filters.get('$or', [])
                    filters['$or'].append({
                        'file_path': {'$contains': mention['name']}
                    })
                elif mention['type'] == 'fichier':
                    file_paths.append(mention['name'])
            
            if file_paths:
                if '$or' not in filters:
                    filters['$or'] = []
                for file_path in file_paths:
                    filters['$or'].append({
                        'file_name': {'$contains': file_path}
                    })
        
        # Filtre par date
        if 'date' in parsed_query.filters:
            # Calculer la date limite
            from datetime import datetime, timedelta
            
            date_filter = parsed_query.filters['date']
            quantity = date_filter['quantity']
            unit = date_filter['unit']
            
            if 'jour' in unit:
                delta = timedelta(days=quantity)
            elif 'semaine' in unit:
                delta = timedelta(weeks=quantity)
            elif 'mois' in unit:
                delta = timedelta(days=quantity * 30)
            else:
                delta = timedelta(days=quantity)
            
            cutoff_date = (datetime.now() - delta).isoformat()
            filters['modification_date'] = {'$gte': cutoff_date}
        
        # Filtre par auteur
        if 'author' in parsed_query.filters:
            filters['author'] = parsed_query.filters['author']
        
        # Filtre par type de document
        if 'document_type' in parsed_query.filters:
            filters['document_type'] = parsed_query.filters['document_type']
        
        return filters
    
    def search_documents(
        self,
        query: str,
        k: int = 10,
        filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Effectue une recherche dans la base vectorielle."""
        try:
            # Utiliser la recherche avec reranking
            results = self.vector_db.search_with_rerank(
                query=query,
                k=k * 2,  # Récupérer plus pour le reranking
                top_k=k,
                filter_dict=filters
            )
            
            return results
            
        except Exception as e:
            st.error(f"Erreur recherche : {e}")
            return []
    
    def get_suggestions(self, partial_query: str) -> List[str]:
        """Retourne des suggestions d'autocomplétion."""
        suggestions = []
        
        # Détecter si on est en train de taper une @mention
        if '@' in partial_query:
            # Extraire la mention partielle
            match = re.search(r'@(\w*)$', partial_query)
            if match:
                partial_mention = match.group(1).lower()
                
                # Chercher dans le cache
                for name in sorted(self.file_cache['all_names']):
                    if name.startswith(partial_mention):
                        # Déterminer le type
                        if name in self.file_cache['dossiers']:
                            suggestions.append(f"@dossier:{name}")
                        else:
                            suggestions.append(f"@fichier:{name}")
                    
                    if len(suggestions) >= 5:
                        break
        
        # Suggestions de mots-clés
        else:
            # Mots-clés fréquents
            keywords = [
                "rédige une plainte",
                "analyse les contradictions",
                "trouve la jurisprudence",
                "extrais les auditions",
                "compare les versions",
                "détecte les anomalies",
                "résume le dossier",
            ]
            
            partial_lower = partial_query.lower()
            for keyword in keywords:
                if keyword.startswith(partial_lower):
                    suggestions.append(keyword)
                
                if len(suggestions) >= 5:
                    break
        
        return suggestions
    
    def format_search_context(
        self,
        documents: List[Dict[str, Any]],
        max_context_length: int = 8000
    ) -> str:
        """Formate les documents trouvés en contexte pour les LLM."""
        context_parts = []
        current_length = 0
        
        for i, doc in enumerate(documents):
            # Extraire les informations
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            
            # Formater l'entrée
            doc_text = f"""
--- Document {i+1} ---
Fichier: {metadata.get('file_name', 'inconnu')}
Page: {metadata.get('page_number', 'N/A')}
Type: {metadata.get('document_type', 'autre')}
Score: {doc.get('rerank_score', doc.get('score', 0)):.2f}

Contenu:
{content}
---
"""
            
            # Vérifier la longueur
            if current_length + len(doc_text) > max_context_length:
                break
            
            context_parts.append(doc_text)
            current_length += len(doc_text)
        
        return "\n".join(context_parts)
    
    def execute_search(
        self,
        parsed_query: SearchQuery,
        dialogue_responses: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Exécute une recherche complète avec interrogation multi-LLM."""
        results = {
            'query': parsed_query,
            'documents': [],
            'llm_responses': {},
            'fusion': None,
            'timestamp': datetime.now(),
            'cost_estimate': 0,
        }
        
        try:
            # 1. Recherche des documents pertinents
            filters = self.build_search_filters(parsed_query)
            documents = self.search_documents(
                query=parsed_query.clean_query,
                k=20,
                filters=filters
            )
            results['documents'] = documents
            
            # 2. Préparer le contexte
            context = self.format_search_context(documents)
            
            # 3. Construire le prompt enrichi
            prompt = self._build_enhanced_prompt(
                parsed_query,
                dialogue_responses
            )
            
            # 4. Estimer le coût
            results['cost_estimate'] = self.llm_manager.estimate_total_cost(
                prompt,
                context,
                parsed_query.models
            )
            
            # 5. Interroger les LLM (simulation pour la démo)
            # En production, utiliser : self.llm_manager.query_multiple(...)
            for model in parsed_query.models:
                results['llm_responses'][model] = {
                    'content': f"Réponse simulée de {model} pour : {parsed_query.clean_query}",
                    'sources': [doc['metadata'].get('file_name', 'inconnu') 
                              for doc in documents[:3]],
                    'confidence': 0.85,
                }
            
            # 6. Fusionner les réponses
            # En production, utiliser le vrai système de fusion
            results['fusion'] = {
                'type': 'synthétique',
                'content': self._generate_synthetic_response(
                    parsed_query,
                    documents,
                    results['llm_responses']
                ),
                'citations': self._extract_citations(documents),
            }
            
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    def _build_enhanced_prompt(
        self,
        parsed_query: SearchQuery,
        dialogue_responses: Dict[str, Any] = None
    ) -> str:
        """Construit un prompt enrichi avec le contexte du dialogue."""
        prompt_parts = []
        
        # Contexte de base
        prompt_parts.append(
            "Tu es un assistant juridique expert en droit pénal des affaires. "
            "Tu dois répondre de manière précise en citant toujours tes sources."
        )
        
        # Ajouter le contexte du dialogue si présent
        if dialogue_responses:
            prompt_parts.append("\nContexte supplémentaire fourni par l'utilisateur :")
            for key, value in dialogue_responses.items():
                if value:
                    prompt_parts.append(f"- {key}: {value}")
        
        # Ajouter l'intention détectée
        if parsed_query.intent == 'redaction':
            prompt_parts.append(
                "\nL'utilisateur souhaite RÉDIGER un document juridique. "
                "Fournis une rédaction complète et professionnelle."
            )
        elif parsed_query.intent == 'analyse':
            prompt_parts.append(
                "\nL'utilisateur souhaite ANALYSER des documents. "
                "Fournis une analyse détaillée avec points forts et faiblesses."
            )
        
        # Ajouter la question
        prompt_parts.append(f"\nQuestion : {parsed_query.clean_query}")
        
        return "\n".join(prompt_parts)
    
    def _generate_synthetic_response(
        self,
        parsed_query: SearchQuery,
        documents: List[Dict[str, Any]],
        llm_responses: Dict[str, Any]
    ) -> str:
        """Génère une réponse synthétique (simulation)."""
        # En production, utiliser le vrai système de fusion
        response_parts = []
        
        # Introduction basée sur l'intention
        if parsed_query.intent == 'redaction':
            response_parts.append(
                "Voici la rédaction demandée, basée sur l'analyse des documents :"
            )
        elif parsed_query.intent == 'analyse':
            response_parts.append(
                "Voici l'analyse détaillée des éléments demandés :"
            )
        else:
            response_parts.append(
                "Voici les éléments trouvés en réponse à votre recherche :"
            )
        
        # Corps de la réponse
        response_parts.append(
            "\n\n**Points clés identifiés :**\n"
            "1. Les documents consultés révèlent plusieurs éléments importants\n"
            "2. Une analyse approfondie montre des patterns récurrents\n"
            "3. Les sources convergent sur les points essentiels\n"
        )
        
        # Citations
        if documents:
            response_parts.append("\n**Sources consultées :**")
            for i, doc in enumerate(documents[:5]):
                metadata = doc.get('metadata', {})
                response_parts.append(
                    f"- {metadata.get('file_name', 'Document')} "
                    f"(page {metadata.get('page_number', 'N/A')})"
                )
        
        return "\n".join(response_parts)
    
    def _extract_citations(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extrait les citations formatées des documents."""
        citations = []
        
        for doc in documents[:10]:  # Limiter aux 10 plus pertinents
            metadata = doc.get('metadata', {})
            
            citation = {
                'content': doc.get('content', '')[:200] + "...",
                'source': {
                    'file': metadata.get('file_name', 'inconnu'),
                    'page': metadata.get('page_number'),
                    'path': metadata.get('file_path'),
                },
                'relevance': doc.get('rerank_score', doc.get('score', 0)),
            }
            
            citations.append(citation)
        
        return citations


class SearchInterface:
    """Interface Streamlit pour la recherche intelligente."""
    
    def __init__(self):
        self.search_engine = IntelligentSearch()
        self.dialogue_manager = DialogueManager()
        
        # État de session
        if 'search_history' not in st.session_state:
            st.session_state.search_history = []
        if 'current_search' not in st.session_state:
            st.session_state.current_search = None
    
    def render_search_bar(self) -> Optional[str]:
        """Affiche la barre de recherche intelligente."""
        # Container pour la barre de recherche
        search_container = st.container()
        
        with search_container:
            # Zone de texte principale
            query = st.text_area(
                "🔍 Recherche intelligente",
                height=100,
                placeholder=(
                    "Exemples :\n"
                    "• @martin analyse les contradictions dans les auditions\n"
                    "• Rédige une plainte pour escroquerie en t'inspirant de @modele_plainte\n"
                    "• Trouve la jurisprudence récente sur le blanchiment depuis 6 mois\n"
                    "• @dossier:corruption compare les versions des témoins"
                ),
                key="main_search_input",
                help="Utilisez @ pour mentionner des dossiers ou fichiers. Appuyez sur Entrée pour lancer."
            )
            
            # Détection de la touche Entrée
            if query and '\n' in query:
                # L'utilisateur a appuyé sur Entrée
                return query.strip()
            
            # Suggestions d'autocomplétion
            if query and not query.endswith('\n'):
                suggestions = self.search_engine.get_suggestions(query)
                if suggestions:
                    selected = st.selectbox(
                        "Suggestions",
                        [""] + suggestions,
                        key="suggestions",
                        label_visibility="collapsed"
                    )
                    
                    if selected:
                        # Remplacer la partie en cours par la suggestion
                        if '@' in query:
                            # Remplacer la dernière mention
                            parts = query.rsplit('@', 1)
                            return parts[0] + selected
            
            # Options de recherche rapides
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔍 Recherche simple", use_container_width=True):
                    return query.strip() if query else None
            
            with col2:
                if st.button("🎯 Recherche guidée", use_container_width=True):
                    st.session_state.show_guided_search = True
                    return None
            
            with col3:
                if st.button("📚 Parcourir", use_container_width=True):
                    st.session_state.show_file_browser = True
                    return None
        
        return None
    
    def render_dialogue(
        self,
        parsed_query: SearchQuery
    ) -> Optional[Dict[str, Any]]:
        """Affiche le dialogue de clarification si nécessaire."""
        # Analyser si on a besoin de clarifications
        analysis = self.dialogue_manager.analyze_query(parsed_query.raw_query)
        
        if not analysis['needs_clarification'] or analysis['confidence'] > 0.8:
            return {}
        
        st.info("💬 J'ai besoin de quelques précisions pour mieux vous aider...")
        
        responses = {}
        
        with st.form("clarification_form"):
            for question in analysis['questions']:
                if question['type'] == 'choice':
                    responses[question['id']] = st.selectbox(
                        question['text'],
                        [""] + question['options'],
                        key=f"q_{question['id']}"
                    )
                elif question['type'] == 'text':
                    responses[question['id']] = st.text_input(
                        question['text'],
                        key=f"q_{question['id']}"
                    )
                elif question['type'] == 'date':
                    responses[question['id']] = st.date_input(
                        question['text'],
                        key=f"q_{question['id']}"
                    )
                elif question['type'] == 'multiselect':
                    responses[question['id']] = st.multiselect(
                        question['text'],
                        question['options'],
                        key=f"q_{question['id']}"
                    )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("✅ Valider", type="primary", use_container_width=True):
                    return responses
            with col2:
                if st.form_submit_button("⚡ Lancer sans précisions", use_container_width=True):
                    return {}
        
        return None
    
    def render_results(self, results: Dict[str, Any]):
        """Affiche les résultats de recherche."""
        if 'error' in results:
            st.error(f"❌ Erreur : {results['error']}")
            return
        
        # Métriques
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📄 Documents trouvés", len(results['documents']))
        with col2:
            st.metric("🤖 Modèles consultés", len(results['llm_responses']))
        with col3:
            st.metric("💰 Coût estimé", f"{results['cost_estimate']:.3f} €")
        with col4:
            st.metric("⏱️ Temps", "2.3s")  # Simulation
        
        # Résultats principaux
        st.markdown("### 📝 Synthèse des résultats")
        
        if results.get('fusion'):
            fusion = results['fusion']
            
            # Afficher le contenu principal
            st.markdown(fusion['content'])
            
            # Citations et sources
            if fusion.get('citations'):
                with st.expander("📚 Sources et citations"):
                    for i, citation in enumerate(fusion['citations']):
                        st.markdown(f"**Source {i+1}**")
                        st.caption(
                            f"📄 {citation['source']['file']} "
                            f"(page {citation['source']['page']})"
                        )
                        st.text(citation['content'])
                        st.markdown("---")
        
        # Réponses individuelles des modèles
        with st.expander("🤖 Réponses détaillées par modèle"):
            tabs = st.tabs(list(results['llm_responses'].keys()))
            
            for tab, (model, response) in zip(tabs, results['llm_responses'].items()):
                with tab:
                    st.markdown(response['content'])
                    
                    if response.get('sources'):
                        st.caption("Sources utilisées :")
                        for source in response['sources']:
                            st.write(f"- 📄 {source}")
        
        # Actions sur les résultats
        st.markdown("### 🎯 Actions")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("📄 Générer document", use_container_width=True):
                st.session_state.generate_from_results = results
                
        with col2:
            if st.button("💾 Sauvegarder", use_container_width=True):
                # Sauvegarder dans l'historique
                st.session_state.search_history.append(results)
                st.success("✅ Recherche sauvegardée")
                
        with col3:
            if st.button("📤 Exporter", use_container_width=True):
                # Exporter en JSON
                json_str = json.dumps(results, indent=2, default=str)
                st.download_button(
                    "📥 Télécharger JSON",
                    json_str,
                    f"recherche_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                
        with col4:
            if st.button("🔄 Nouvelle recherche", use_container_width=True):
                st.session_state.current_search = None
                st.rerun()
# Ajout à core/search/intelligent_search.py
# Ajouter cette classe à la fin du fichier intelligent_search.py

class SearchInterface:
    """Interface simplifiée pour la recherche depuis Streamlit."""
    
    def __init__(self):
        self.search_engine = IntelligentSearch()
        self.dialogue_manager = DialogueManager()
        
        # Initialiser l'état de session
        if 'search_history' not in st.session_state:
            st.session_state.search_history = []
        if 'current_search' not in st.session_state:
            st.session_state.current_search = None
    
    def render_search_bar(
        self,
        placeholder: str = "Recherchez avec @dossier ou @fichier...",
        key: str = "main_search"
    ) -> Optional[str]:
        """
        Affiche la barre de recherche principale.
        
        Returns:
            La requête si soumise, None sinon
        """
        # Container pour la barre de recherche
        search_container = st.container()
        
        with search_container:
            # Barre de recherche avec autocomplétion
            col1, col2 = st.columns([5, 1])
            
            with col1:
                query = st.text_area(
                    "Recherche",
                    placeholder=placeholder,
                    height=100,
                    key=f"{key}_input",
                    help="Utilisez @ pour les mentions, Ex: @dossier:martin @fichier:pv"
                )
            
            with col2:
                st.write("")  # Espaceur
                st.write("")  # Espaceur
                search_button = st.button(
                    "🔍 Rechercher",
                    key=f"{key}_button",
                    use_container_width=True,
                    type="primary"
                )
            
            # Suggestions d'autocomplétion
            if query and '@' in query:
                suggestions = self.search_engine.get_suggestions(query)
                if suggestions:
                    st.caption("💡 Suggestions:")
                    cols = st.columns(min(len(suggestions), 3))
                    for i, suggestion in enumerate(suggestions[:3]):
                        with cols[i]:
                            if st.button(suggestion, key=f"sug_{key}_{i}"):
                                # Remplacer la dernière partie par la suggestion
                                parts = query.rsplit('@', 1)
                                new_query = parts[0] + suggestion
                                st.session_state[f"{key}_input"] = new_query
                                st.rerun()
            
            # Retourner la requête si bouton cliqué ou Entrée
            if search_button and query:
                return query
            
            return None
    
    def render_model_selector(
        self,
        default_models: List[str] = None,
        key: str = "model_selector"
    ) -> List[str]:
        """
        Affiche le sélecteur de modèles IA.
        
        Returns:
            Liste des modèles sélectionnés
        """
        available_models = self.search_engine.llm_manager.get_available_models()
        
        if not available_models:
            st.warning("⚠️ Aucun modèle IA disponible. Vérifiez les clés API.")
            return []
        
        # Valeurs par défaut
        if default_models is None:
            default_models = available_models[:2]  # Les 2 premiers
        
        # Sélecteur
        selected = st.multiselect(
            "Modèles IA à interroger",
            available_models,
            default=default_models,
            key=key,
            help="Sélectionnez plusieurs modèles pour comparer les réponses"
        )
        
        # Afficher les capacités des modèles sélectionnés
        if selected:
            with st.expander("ℹ️ Capacités des modèles"):
                for model in selected:
                    caps = self.search_engine.llm_manager.get_model_capabilities(model)
                    st.write(f"**{model}**")
                    
                    cols = st.columns(4)
                    with cols[0]:
                        st.caption(f"Tokens: {caps.get('max_tokens', 'N/A'):,}")
                    with cols[1]:
                        st.caption(f"Vision: {'✅' if caps.get('vision') else '❌'}")
                    with cols[2]:
                        st.caption(f"Web: {'✅' if caps.get('web_search') else '❌'}")
                    with cols[3]:
                        cost_level = caps.get('cost_level', 'unknown')
                        cost_emoji = {
                            'very_low': '💚',
                            'low': '🟢',
                            'medium': '🟡',
                            'high': '🔴'
                        }.get(cost_level, '❓')
                        st.caption(f"Coût: {cost_emoji}")
        
        return selected
    
    def render_search_options(self, key: str = "search_options") -> Dict[str, Any]:
        """
        Affiche les options de recherche avancées.
        
        Returns:
            Dict avec les options sélectionnées
        """
        with st.expander("⚙️ Options avancées"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                search_type = st.selectbox(
                    "Type de recherche",
                    ["Sémantique", "Mots-clés", "Hybride"],
                    key=f"{key}_type"
                )
                
                max_results = st.number_input(
                    "Nombre de résultats",
                    min_value=5,
                    max_value=50,
                    value=10,
                    step=5,
                    key=f"{key}_max"
                )
            
            with col2:
                date_filter = st.selectbox(
                    "Période",
                    ["Tous", "7 derniers jours", "30 derniers jours", "6 mois", "1 an"],
                    key=f"{key}_date"
                )
                
                doc_types = st.multiselect(
                    "Types de documents",
                    ["Tous", "PDF", "Word", "Emails", "Images"],
                    default=["Tous"],
                    key=f"{key}_types"
                )
            
            with col3:
                fusion_strategy = st.selectbox(
                    "Stratégie de fusion",
                    ["synthétique", "comparatif", "contradictoire", "exhaustif", "argumentatif"],
                    key=f"{key}_fusion"
                )
                
                include_sources = st.checkbox(
                    "Inclure les sources",
                    value=True,
                    key=f"{key}_sources"
                )
        
        return {
            'search_type': search_type,
            'max_results': max_results,
            'date_filter': date_filter,
            'doc_types': doc_types,
            'fusion_strategy': fusion_strategy,
            'include_sources': include_sources
        }
    
    async def execute_search(
        self,
        query: str,
        models: List[str],
        options: Dict[str, Any],
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Exécute une recherche complète.
        
        Returns:
            Résultats de la recherche
        """
        # Parser la requête
        parsed_query = self.search_engine.parse_query(query)
        
        # Recherche vectorielle
        if progress_callback:
            progress_callback(0.2, "Recherche dans la base documentaire...")
        
        documents = self.search_engine.search_documents(
            query=parsed_query.clean_query,
            filters=parsed_query.filters,
            k=options.get('max_results', 10)
        )
        
        # Préparer le contexte
        context = self.search_engine.format_search_context(documents)
        
        # Interroger les LLM
        if progress_callback:
            progress_callback(0.5, "Interrogation des IA...")
        
        llm_responses = await self.search_engine.llm_manager.query_multiple(
            prompt=query,
            context=context,
            selected_models=models,
            progress_callback=lambda p, m: progress_callback(0.5 + p * 0.4, m) if progress_callback else None
        )
        
        # Fusionner les réponses
        if progress_callback:
            progress_callback(0.9, "Fusion des réponses...")
        
        fused_response = self.search_engine.llm_manager.fuse_responses(
            llm_responses['responses'],
            strategy=options.get('fusion_strategy', 'synthétique')
        )
        
        # Compiler les résultats
        results = {
            'query': query,
            'parsed_query': parsed_query,
            'documents': documents,
            'llm_responses': llm_responses,
            'fused_response': fused_response,
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'models_used': models,
                'options': options,
                'total_cost': llm_responses['metadata'].get('total_cost', 0),
                'total_tokens': llm_responses['metadata'].get('total_tokens', 0)
            }
        }
        
        # Ajouter à l'historique
        st.session_state.search_history.append({
            'query': query,
            'timestamp': datetime.now(),
            'models': models,
            'cost': results['metadata']['total_cost']
        })
        
        if progress_callback:
            progress_callback(1.0, "Terminé!")
        
        return results
    
    def render_results(self, results: Dict[str, Any]):
        """Affiche les résultats de recherche."""
        # Métriques
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Documents trouvés",
                len(results['documents'])
            )
        
        with col2:
            st.metric(
                "Modèles utilisés",
                len(results['metadata']['models_used'])
            )
        
        with col3:
            st.metric(
                "Tokens utilisés",
                f"{results['metadata']['total_tokens']:,}"
            )
        
        with col4:
            cost = results['metadata']['total_cost']
            st.metric(
                "Coût estimé",
                f"{cost:.4f}$" if cost > 0 else "Gratuit"
            )
        
        # Réponse fusionnée
        st.markdown("### 📝 Synthèse des réponses")
        st.markdown(results['fused_response'])
        
        # Documents sources
        if results['metadata']['options'].get('include_sources'):
            with st.expander("📚 Documents sources"):
                for i, doc in enumerate(results['documents'][:5]):
                    st.markdown(f"**{i+1}. {doc.get('metadata', {}).get('filename', 'Document')}**")
                    st.caption(f"Page {doc.get('metadata', {}).get('page_number', 'N/A')} | Score: {doc.get('score', 0):.2f}")
                    st.text(doc.get('content', '')[:200] + "...")
                    st.markdown("---")
        
        # Réponses individuelles
        with st.expander("🤖 Réponses détaillées par modèle"):
            for model, response in results['llm_responses']['responses'].items():
                if not response.get('error'):
                    st.markdown(f"### {model}")
                    st.markdown(response.get('content', ''))
                    
                    # Métriques du modèle
                    cols = st.columns(3)
                    with cols[0]:
                        st.caption(f"Tokens: {response.get('tokens_used', 0)}")
                    with cols[1]:
                        st.caption(f"Temps: {response.get('time', 0):.2f}s")
                    with cols[2]:
                        st.caption(f"Coût: ${response.get('cost', 0):.4f}")
                    
                    st.markdown("---")
    
    def render_search_history(self):
        """Affiche l'historique des recherches."""
        if st.session_state.search_history:
            st.markdown("### 📜 Historique récent")
            
            for i, search in enumerate(reversed(st.session_state.search_history[-5:])):
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.text(search['query'][:50] + "..." if len(search['query']) > 50 else search['query'])
                    
                    with col2:
                        st.caption(search['timestamp'].strftime("%H:%M"))
                    
                    with col3:
                        if st.button("🔄", key=f"repeat_{i}"):
                            st.session_state.current_search = search['query']
                            st.rerun()
        else:
            st.info("Aucune recherche récente")

# Export mis à jour
__all__ = ['IntelligentSearch', 'SearchQuery', 'SearchInterface']
