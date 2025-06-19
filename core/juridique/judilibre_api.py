# core/juridique/judilibre_api.py
"""
Interface avec l'API Judilibre pour la recherche de jurisprudence.
Version avec authentification OAuth2 complète.
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from .oauth_client import get_oauth_client


class JudilibreAPI:
    """Client pour l'API Judilibre avec OAuth2."""
    
    def __init__(self):
        # Utiliser le client OAuth2
        self.oauth_client = get_oauth_client("judilibre")
        
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
        max_results: int = 20,
        page: int = 0
    ) -> Dict[str, Any]:
        """
        Recherche dans la jurisprudence de la Cour de cassation.
        
        Args:
            query: Termes de recherche
            chamber: Chambre (criminelle, civile, commerciale, sociale)
            formation: Formation (plénière, mixte, section, ordinaire)
            date_start: Date début (YYYY-MM-DD)
            date_end: Date fin (YYYY-MM-DD)
            themes: Liste de thèmes/matières
            operator: Opérateur logique (AND, OR, EXACT)
            sort: Tri (score, date_asc, date_desc)
            max_results: Nombre maximum de résultats par page
            page: Numéro de page (commence à 0)
        
        Returns:
            Dict avec les résultats et métadonnées
        """
        self._rate_limit()
        
        # Construction des paramètres
        params = {
            "query": query,
            "operator": operator,
            "sort": sort,
            "page_size": min(max_results, 50),
            "page": page
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
            params["theme"] = ",".join(themes)
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint="/search",
                params=params
            )
            
            data = response.json()
            
            # Formater les résultats
            results = []
            for item in data.get("results", []):
                results.append(self._format_decision(item))
            
            return {
                'results': results,
                'total': data.get('total_results', 0),
                'page': data.get('page', 0),
                'page_size': data.get('page_size', max_results),
                'total_pages': data.get('total_pages', 1),
                'query': query,
                'took_ms': data.get('took', 0)
            }
            
        except Exception as e:
            print(f"Erreur Judilibre API: {e}")
            return {
                'results': [],
                'total': 0,
                'error': str(e)
            }
    
    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère une décision spécifique par son ID.
        
        Args:
            decision_id: Identifiant de la décision
        
        Returns:
            Détails complets de la décision
        """
        self._rate_limit()
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint=f"/decision?id={decision_id}"
            )
            
            data = response.json()
            return self._format_decision(data, detailed=True)
            
        except Exception as e:
            print(f"Erreur récupération décision: {e}")
            return None
    
    def search_by_number(self, pourvoi_number: str) -> List[Dict[str, Any]]:
        """
        Recherche une décision par numéro de pourvoi.
        
        Args:
            pourvoi_number: Numéro de pourvoi (ex: "19-12.345")
        
        Returns:
            Liste des décisions correspondantes
        """
        # Utiliser une recherche exacte sur le numéro
        result = self.search(
            query=f'"{pourvoi_number}"',
            operator="EXACT",
            max_results=10
        )
        
        return result.get('results', [])
    
    def search_by_article(
        self,
        code: str,
        article: str,
        date_start: str = None,
        date_end: str = None,
        chamber: str = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Recherche les décisions citant un article spécifique.
        
        Args:
            code: Code (ex: "code pénal", "code civil")
            article: Numéro d'article (ex: "121-3", "1240")
            date_start: Date début
            date_end: Date fin
            chamber: Chambre spécifique
            max_results: Nombre maximum de résultats
        
        Returns:
            Liste des décisions citant l'article
        """
        # Construction de la requête
        # Judilibre comprend les références d'articles
        query = f'"{code}" AND "{article}"'
        
        result = self.search(
            query=query,
            chamber=chamber,
            date_start=date_start,
            date_end=date_end,
            max_results=max_results,
            sort="date_desc"
        )
        
        return result.get('results', [])
    
    def get_related_decisions(
        self,
        decision_id: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Trouve des décisions similaires ou liées.
        
        Args:
            decision_id: ID de la décision de référence
            max_results: Nombre maximum de résultats
        
        Returns:
            Liste des décisions similaires
        """
        self._rate_limit()
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint=f"/related",
                params={
                    "id": decision_id,
                    "size": max_results
                }
            )
            
            data = response.json()
            results = []
            
            for item in data.get("results", []):
                results.append(self._format_decision(item))
            
            return results
            
        except Exception as e:
            print(f"Erreur recherche décisions liées: {e}")
            return []
    
    def export_decision(
        self,
        decision_id: str,
        format: str = "pdf"
    ) -> Optional[bytes]:
        """
        Exporte une décision dans le format souhaité.
        
        Args:
            decision_id: ID de la décision
            format: Format d'export ("pdf", "rtf", "xml")
        
        Returns:
            Contenu du fichier ou None
        """
        self._rate_limit()
        
        if format not in ["pdf", "rtf", "xml"]:
            raise ValueError(f"Format non supporté: {format}")
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint=f"/export/{decision_id}",
                params={"format": format}
            )
            
            return response.content
            
        except Exception as e:
            print(f"Erreur export décision: {e}")
            return None
    
    def get_statistics(
        self,
        query: str = None,
        chamber: str = None,
        year: int = None,
        themes: List[str] = None
    ) -> Dict[str, Any]:
        """
        Obtient des statistiques sur les décisions.
        
        Args:
            query: Filtre de recherche
            chamber: Chambre spécifique
            year: Année spécifique
            themes: Thèmes spécifiques
        
        Returns:
            Statistiques agrégées
        """
        self._rate_limit()
        
        params = {}
        if query:
            params["query"] = query
        if chamber:
            params["chamber"] = chamber
        if year:
            params["year"] = year
        if themes:
            params["themes"] = ",".join(themes)
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint="/stats",
                params=params
            )
            
            return response.json()
            
        except Exception as e:
            print(f"Erreur récupération statistiques: {e}")
            return {}
    
    def _format_decision(self, data: Dict[str, Any], detailed: bool = False) -> Dict[str, Any]:
        """
        Formate une décision pour uniformiser la structure.
        
        Args:
            data: Données brutes de l'API
            detailed: Si True, inclut tous les détails
        
        Returns:
            Décision formatée
        """
        # Format de base
        decision = {
            'id': data.get('id'),
            'numero': data.get('number'),
            'date': data.get('date_decision'),
            'chambre': data.get('chamber'),
            'formation': data.get('formation'),
            'solution': data.get('solution'),
            'sommaire': data.get('summary', ''),
            'ecli': data.get('ecli'),
            'pourvoi': data.get('pourvoi_number'),
            'themes': data.get('themes', []),
            'url': data.get('url'),
            'bulletin': data.get('bulletin'),
            'importance': data.get('importance', 'normale')
        }
        
        # Détails supplémentaires si demandés
        if detailed:
            decision.update({
                'texte_integral': data.get('text', ''),
                'president': data.get('president'),
                'rapporteur': data.get('rapporteur'),
                'avocat_general': data.get('avocat_general'),
                'avocats': data.get('avocats', []),
                'moyens': data.get('moyens', []),
                'textes_appliques': data.get('textes_appliques', []),
                'textes_vises': data.get('textes_vises', []),
                'rapprochements': data.get('rapprochements', []),
                'commentaires': data.get('commentaires', []),
                'titrage': data.get('titrage', {}),
                'analyses': data.get('analyses', [])
            })
        
        return decision
    
    def build_advanced_query(
        self,
        must_contain: List[str] = None,
        should_contain: List[str] = None,
        must_not_contain: List[str] = None,
        exact_phrases: List[str] = None,
        proximity: Dict[str, int] = None
    ) -> str:
        """
        Construit une requête avancée avec opérateurs.
        
        Args:
            must_contain: Mots qui doivent être présents (AND)
            should_contain: Au moins un de ces mots (OR)
            must_not_contain: Mots à exclure (NOT)
            exact_phrases: Phrases exactes à rechercher
            proximity: Recherche de proximité {"terme1 terme2": distance}
        
        Returns:
            Requête formatée pour l'API
        """
        query_parts = []
        
        # Mots obligatoires
        if must_contain:
            query_parts.append(" ET ".join(must_contain))
        
        # Au moins un mot
        if should_contain:
            or_part = "(" + " OU ".join(should_contain) + ")"
            query_parts.append(or_part)
        
        # Exclusions
        if must_not_contain:
            for word in must_not_contain:
                query_parts.append(f"NON {word}")
        
        # Phrases exactes
        if exact_phrases:
            for phrase in exact_phrases:
                query_parts.append(f'"{phrase}"')
        
        # Proximité
        if proximity:
            for terms, distance in proximity.items():
                # Format: "terme1 PRES/n terme2"
                words = terms.split()
                if len(words) >= 2:
                    query_parts.append(f"{words[0]} PRES/{distance} {words[1]}")
        
        return " ET ".join(query_parts) if query_parts else ""


# Export
__all__ = ['JudilibreAPI']
