# core/search/dialogue_manager.py
"""
Gestionnaire de dialogue pour l'interaction avec l'utilisateur.
"""
import streamlit as st
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class DialogueState:
    """État du dialogue avec l'utilisateur."""
    query: str
    clarifications_needed: List[Dict[str, Any]] = field(default_factory=list)
    user_responses: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    ready_to_execute: bool = False
    round: int = 0


class DialogueManager:
    """Gère le dialogue interactif avec l'utilisateur."""
    
    def __init__(self):
        self.max_rounds = 3  # Maximum de tours de clarification
        
        # Questions types selon le contexte
        self.question_templates = {
            'redaction': [
                {
                    'key': 'jurisdiction',
                    'question': "Pour quelle juridiction préparez-vous cet acte ?",
                    'options': ["Tribunal correctionnel", "Cour d'appel", "Cour de cassation", "Juge d'instruction"],
                    'required': True
                },
                {
                    'key': 'deadline',
                    'question': "Avez-vous une date limite de dépôt ?",
                    'type': 'date',
                    'required': False
                },
                {
                    'key': 'tone',
                    'question': "Quel ton souhaitez-vous adopter ?",
                    'options': ["Très formel", "Formel", "Assertif", "Combatif"],
                    'default': "Formel"
                }
            ],
            'analyse': [
                {
                    'key': 'focus',
                    'question': "Sur quoi voulez-vous concentrer l'analyse ?",
                    'options': ["Contradictions", "Chronologie", "Éléments constitutifs", "Moyens de défense"],
                    'multiple': True,
                    'required': True
                },
                {
                    'key': 'depth',
                    'question': "Quel niveau de détail souhaitez-vous ?",
                    'options': ["Synthèse rapide", "Analyse standard", "Analyse approfondie"],
                    'default': "Analyse standard"
                }
            ],
            'recherche': [
                {
                    'key': 'period',
                    'question': "Sur quelle période temporelle ?",
                    'options': ["3 derniers mois", "6 derniers mois", "1 an", "Toute période"],
                    'default': "6 derniers mois"
                },
                {
                    'key': 'sources',
                    'question': "Quelles sources privilégier ?",
                    'options': ["Documents internes", "Jurisprudence", "Les deux"],
                    'default': "Les deux"
                }
            ]
        }
    
    def needs_clarification(self, query: str, intent: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Détermine si la requête nécessite des clarifications.
        
        Returns:
            (needs_clarification, questions_to_ask)
        """
        # Analyser ce qui manque dans la requête
        missing_info = self._analyze_missing_info(query, intent)
        
        if not missing_info:
            return False, []
        
        # Sélectionner les questions pertinentes
        questions = []
        template_questions = self.question_templates.get(intent, [])
        
        for q in template_questions:
            if q['key'] in missing_info or q.get('required', False):
                # Vérifier si l'info n'est pas déjà dans la requête
                if not self._info_in_query(query, q['key']):
                    questions.append(q)
        
        return len(questions) > 0, questions[:3]  # Max 3 questions à la fois
    
    def _analyze_missing_info(self, query: str, intent: str) -> List[str]:
        """Analyse les informations manquantes dans la requête."""
        missing = []
        query_lower = query.lower()
        
        # Selon l'intention
        if intent == 'redaction':
            # Vérifier la juridiction
            jurisdictions = ['tribunal', 'cour', 'juge', 'cassation', 'appel']
            if not any(j in query_lower for j in jurisdictions):
                missing.append('jurisdiction')
            
            # Vérifier si deadline mentionnée
            if not any(word in query_lower for word in ['avant', 'deadline', 'date limite', 'délai']):
                missing.append('deadline')
        
        elif intent == 'analyse':
            # Vérifier le focus
            if not any(word in query_lower for word in ['contradiction', 'chronologie', 'élément', 'défense']):
                missing.append('focus')
        
        elif intent == 'recherche':
            # Vérifier la période
            if not any(word in query_lower for word in ['mois', 'année', 'depuis', 'entre']):
                missing.append('period')
        
        return missing
    
    def _info_in_query(self, query: str, info_key: str) -> bool:
        """Vérifie si une information est déjà présente dans la requête."""
        query_lower = query.lower()
        
        info_patterns = {
            'jurisdiction': ['tribunal', 'cour', 'juge', 'cassation', 'appel'],
            'deadline': ['avant', 'deadline', 'date limite', 'délai', 'dépôt'],
            'tone': ['formel', 'assertif', 'combatif', 'ton'],
            'focus': ['contradiction', 'chronologie', 'élément', 'défense'],
            'period': ['mois', 'année', 'depuis', 'entre', 'dernier'],
            'sources': ['interne', 'jurisprudence', 'document', 'source']
        }
        
        patterns = info_patterns.get(info_key, [])
        return any(pattern in query_lower for pattern in patterns)
    
    def process_user_responses(
        self,
        state: DialogueState,
        responses: Dict[str, Any]
    ) -> DialogueState:
        """Traite les réponses de l'utilisateur."""
        # Mettre à jour l'état
        state.user_responses.update(responses)
        state.round += 1
        
        # Vérifier si on a assez d'informations
        if self._has_sufficient_info(state) or state.round >= self.max_rounds:
            state.ready_to_execute = True
        else:
            # Peut-être d'autres questions
            _, new_questions = self.needs_clarification(
                state.query,
                state.context.get('intent', 'recherche')
            )
            state.clarifications_needed = new_questions
        
        return state
    
    def _has_sufficient_info(self, state: DialogueState) -> bool:
        """Vérifie si on a suffisamment d'informations pour exécuter."""
        intent = state.context.get('intent', 'recherche')
        required_fields = []
        
        # Déterminer les champs requis selon l'intention
        for q in self.question_templates.get(intent, []):
            if q.get('required', False):
                required_fields.append(q['key'])
        
        # Vérifier que tous les champs requis ont une réponse
        for field in required_fields:
            if field not in state.user_responses:
                return False
        
        return True
    
    def generate_confirmation_message(self, state: DialogueState) -> str:
        """Génère un message de confirmation avant exécution."""
        intent = state.context.get('intent', 'recherche')
        responses = state.user_responses
        
        msg = f"Je vais {intent} avec les paramètres suivants :\n\n"
        
        # Formatter les réponses
        for key, value in responses.items():
            label = self._get_field_label(key)
            if isinstance(value, list):
                value = ", ".join(value)
            msg += f"• **{label}** : {value}\n"
        
        msg += "\n*Cliquez sur Exécuter pour lancer la tâche.*"
        
        return msg
    
    def _get_field_label(self, key: str) -> str:
        """Obtient le label français pour un champ."""
        labels = {
            'jurisdiction': 'Juridiction',
            'deadline': 'Date limite',
            'tone': 'Ton',
            'focus': 'Focus',
            'depth': 'Niveau de détail',
            'period': 'Période',
            'sources': 'Sources'
        }
        return labels.get(key, key)


# core/juridique/legifrance_api.py
"""
Interface avec l'API Legifrance pour la recherche de textes juridiques.
"""
import os
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import time


class LegifranceAPI:
    """Client pour l'API Legifrance."""
    
    def __init__(self):
        self.token = os.getenv("LEGIFRANCE_TOKEN")
        if not self.token:
            raise ValueError("LEGIFRANCE_TOKEN non configuré")
        
        self.base_url = "https://api.piste.gouv.fr/cassation/judilibre/v1"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Limites de l'API
        self.rate_limit = 10  # requêtes par seconde
        self.last_request = 0
    
    def _rate_limit(self):
        """Applique la limitation de débit."""
        elapsed = time.time() - self.last_request
        if elapsed < 1/self.rate_limit:
            time.sleep(1/self.rate_limit - elapsed)
        self.last_request = time.time()
    
    def search_codes(
        self,
        query: str,
        code: str = None,
        date_start: str = None,
        date_end: str = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Recherche dans les codes juridiques.
        
        Args:
            query: Texte de recherche
            code: Code spécifique (PENAL, PROCEDURE_PENALE, etc.)
            date_start: Date de début (YYYY-MM-DD)
            date_end: Date de fin (YYYY-MM-DD)
            max_results: Nombre maximum de résultats
        
        Returns:
            Liste des articles trouvés
        """
        self._rate_limit()
        
        # Construction de la requête
        params = {
            "q": query,
            "pageSize": min(max_results, 50),
            "sort": "pertinence"
        }
        
        if code:
            params["code"] = code
        
        if date_start:
            params["dateDebut"] = date_start
        
        if date_end:
            params["dateFin"] = date_end
        
        try:
            response = requests.get(
                f"{self.base_url}/search/code",
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("results", []):
                results.append({
                    'id': item.get('id'),
                    'titre': item.get('titre'),
                    'numero': item.get('numero'),
                    'texte': item.get('texte'),
                    'code': item.get('code'),
                    'date_vigueur': item.get('dateVigueur'),
                    'url': item.get('url'),
                    'score': item.get('score', 0)
                })
            
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur Legifrance API: {e}")
            return []
    
    def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un article spécifique par son ID.
        
        Args:
            article_id: Identifiant de l'article
        
        Returns:
            Détails de l'article ou None
        """
        self._rate_limit()
        
        try:
            response = requests.get(
                f"{self.base_url}/consult/article/{article_id}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'id': data.get('id'),
                'titre': data.get('titre'),
                'numero': data.get('numero'),
                'texte': data.get('texte'),
                'code': data.get('code'),
                'date_vigueur': data.get('dateVigueur'),
                'versions': data.get('versions', []),
                'liens': data.get('liens', []),
                'notes': data.get('notes', [])
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur récupération article: {e}")
            return None
    
    def search_jurisprudence(
        self,
        query: str,
        juridiction: str = None,
        date_start: str = None,
        date_end: str = None,
        themes: List[str] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Recherche dans la jurisprudence.
        
        Args:
            query: Texte de recherche
            juridiction: Filtre par juridiction
            date_start: Date de début
            date_end: Date de fin
            themes: Thèmes juridiques
            max_results: Nombre maximum de résultats
        
        Returns:
            Liste des décisions trouvées
        """
        # Note: Endpoint différent pour la jurisprudence
        # Utiliser Judilibre API pour ça
        return []


# core/juridique/judilibre_api.py
"""
Interface avec l'API Judilibre pour la recherche de jurisprudence.
"""
import os
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import time


class JudilibreAPI:
    """Client pour l'API Judilibre."""
    
    def __init__(self):
        self.token = os.getenv("JUDILIBRE_TOKEN")
        if not self.token:
            raise ValueError("JUDILIBRE_TOKEN non configuré")
        
        self.base_url = "https://api.piste.gouv.fr/cassation/judilibre/v1"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }
        
        # Configuration
        self.rate_limit = 5  # requêtes par seconde
        self.last_request = 0
    
    def _rate_limit(self):
        """Applique la limitation de débit."""
        elapsed = time.time() - self.last_request
        if elapsed < 1/self.rate_limit:
            time.sleep(1/self.rate_limit - elapsed)
        self.last_request = time.time()
    
    def search(
        self,
        query: str,
        chamber: str = None,
        formation: str = None,
        date_start: str = None,
        date_end: str = None,
        themes: List[str] = None,
        operator: str = "AND",
        sort: str = "score",
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Recherche dans la jurisprudence de la Cour de cassation.
        
        Args:
            query: Termes de recherche
            chamber: Chambre (criminelle, commerciale, civile, sociale)
            formation: Formation (plénière, mixte, section, ordinaire)
            date_start: Date début (YYYY-MM-DD)
            date_end: Date fin (YYYY-MM-DD)
            themes: Liste de thèmes
            operator: Opérateur logique (AND, OR)
            sort: Tri (score, date_asc, date_desc)
            max_results: Nombre maximum de résultats
        
        Returns:
            Liste des décisions trouvées
        """
        self._rate_limit()
        
        # Construction des paramètres
        params = {
            "query": query,
            "operator": operator,
            "order": sort,
            "page_size": min(max_results, 50),
            "page": 0
        }
        
        # Filtres optionnels
        if chamber:
            params["chamber"] = chamber
        
        if formation:
            params["formation"] = formation
        
        if date_start:
            params["date_start"] = date_start
        
        if date_end:
            params["date_end"] = date_end
        
        if themes:
            params["themes"] = ",".join(themes)
        
        try:
            response = requests.get(
                f"{self.base_url}/search",
                headers=self.headers,
                params=params,
                timeout=15
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("results", []):
                results.append({
                    'id': item.get('id'),
                    'numero': item.get('number'),
                    'date': item.get('date_decision'),
                    'chambre': item.get('chamber'),
                    'formation': item.get('formation'),
                    'solution': item.get('solution'),
                    'sommaire': item.get('summary', ''),
                    'texte_integral': item.get('text', ''),
                    'themes': item.get('themes', []),
                    'url': item.get('url'),
                    'score': item.get('score', 0),
                    'pourvoi': item.get('pourvoi_number'),
                    'ecli': item.get('ecli')
                })
            
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur Judilibre API: {e}")
            return []
    
    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère une décision spécifique.
        
        Args:
            decision_id: Identifiant de la décision
        
        Returns:
            Détails complets de la décision
        """
        self._rate_limit()
        
        try:
            response = requests.get(
                f"{self.base_url}/decision/{decision_id}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'id': data.get('id'),
                'numero': data.get('number'),
                'date': data.get('date_decision'),
                'chambre': data.get('chamber'),
                'formation': data.get('formation'),
                'president': data.get('president'),
                'rapporteur': data.get('rapporteur'),
                'avocat_general': data.get('avocat_general'),
                'avocats': data.get('avocats', []),
                'solution': data.get('solution'),
                'sommaire': data.get('summary', ''),
                'texte_integral': data.get('text', ''),
                'moyens': data.get('moyens', []),
                'themes': data.get('themes', []),
                'textes_appliques': data.get('textes_appliques', []),
                'rapprochements': data.get('rapprochements', []),
                'url': data.get('url'),
                'pourvoi': data.get('pourvoi_number'),
                'ecli': data.get('ecli'),
                'bulletin': data.get('bulletin'),
                'rapport': data.get('rapport')
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur récupération décision: {e}")
            return None
    
    def search_by_article(
        self,
        code: str,
        article: str,
        date_start: str = None,
        date_end: str = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Recherche les décisions citant un article spécifique.
        
        Args:
            code: Code (ex: "code pénal")
            article: Numéro d'article (ex: "121-3")
            date_start: Date début
            date_end: Date fin
            max_results: Nombre maximum de résultats
        
        Returns:
            Liste des décisions citant l'article
        """
        # Construction de la requête
        query = f'"{code}" AND "{article}"'
        
        return self.search(
            query=query,
            date_start=date_start,
            date_end=date_end,
            max_results=max_results,
            sort="date_desc"
        )
    
    def get_statistics(
        self,
        query: str = None,
        chamber: str = None,
        year: int = None
    ) -> Dict[str, Any]:
        """
        Obtient des statistiques sur les décisions.
        
        Args:
            query: Filtre de recherche
            chamber: Chambre spécifique
            year: Année spécifique
        
        Returns:
            Statistiques agrégées
        """
        # Cette fonctionnalité pourrait nécessiter plusieurs requêtes
        # ou un endpoint spécifique selon l'API
        
        stats = {
            'total': 0,
            'par_chambre': {},
            'par_formation': {},
            'par_annee': {},
            'themes_frequents': []
        }
        
        # Implémentation simplifiée
        # En pratique, faire des requêtes avec agrégations
        
        return stats


# Export
__all__ = ['DialogueManager', 'DialogueState', 'LegifranceAPI', 'JudilibreAPI']
