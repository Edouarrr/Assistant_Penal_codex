# core/juridique/legifrance_api.py
"""
Interface avec l'API Legifrance pour la recherche de textes juridiques.
Version avec authentification OAuth2 complète.
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from .oauth_client import get_oauth_client


class LegifranceAPI:
    """Client pour l'API Legifrance avec OAuth2."""
    
    def __init__(self):
        # Utiliser le client OAuth2
        self.oauth_client = get_oauth_client("legifrance")
        
        # Configuration de base
        self.base_path = "/consult"  # Path de base pour Legifrance
        
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
        
        # Construction des paramètres
        params = {
            "q": query,
            "pageSize": min(max_results, 50),
            "sort": "pertinence"
        }
        
        if code:
            params["fond"] = code  # Legifrance utilise "fond" pour le code
        
        if date_start:
            params["dateDebut"] = date_start
        
        if date_end:
            params["dateFin"] = date_end
        
        try:
            # Utiliser le client OAuth2
            response = self.oauth_client.make_request(
                method="GET",
                endpoint="/search/code",
                params=params
            )
            
            data = response.json()
            results = []
            
            for item in data.get("results", []):
                results.append({
                    'id': item.get('id'),
                    'titre': item.get('titre'),
                    'numero': item.get('numeroArticle'),
                    'texte': item.get('texteArticle'),
                    'code': item.get('nomCode'),
                    'date_vigueur': item.get('dateDebut'),
                    'etat': item.get('etatTexte'),
                    'url': item.get('url'),
                    'nota': item.get('nota', []),
                    'liens': item.get('liens', [])
                })
            
            return results
            
        except Exception as e:
            print(f"Erreur Legifrance API: {e}")
            return []
    
    def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un article spécifique par son ID.
        
        Args:
            article_id: Identifiant de l'article (format: LEGIARTI...)
        
        Returns:
            Détails de l'article ou None
        """
        self._rate_limit()
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint=f"/consult/getArticle?id={article_id}"
            )
            
            data = response.json()
            
            return {
                'id': data.get('id'),
                'titre': data.get('titre'),
                'numero': data.get('num'),
                'texte': self._clean_article_text(data.get('texte', '')),
                'code': data.get('codeNom'),
                'date_debut': data.get('dateDebut'),
                'date_fin': data.get('dateFin'),
                'etat': data.get('etat'),
                'versions': data.get('listeVersions', []),
                'liens': data.get('liens', []),
                'structure': data.get('structure', {}),
                'nota': data.get('nota', []),
                'historique': data.get('historique', [])
            }
            
        except Exception as e:
            print(f"Erreur récupération article: {e}")
            return None
    
    def search_jurisprudence(
        self,
        query: str,
        juridiction: str = None,
        date_start: str = None,
        date_end: str = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Recherche dans la jurisprudence constitutionnelle et administrative.
        
        Args:
            query: Texte de recherche
            juridiction: CC (Conseil Constitutionnel), CE (Conseil d'État)
            date_start: Date de début
            date_end: Date de fin
            max_results: Nombre maximum de résultats
        
        Returns:
            Liste des décisions trouvées
        """
        self._rate_limit()
        
        params = {
            "q": query,
            "pageSize": min(max_results, 50)
        }
        
        if juridiction:
            params["juridiction"] = juridiction
            
        if date_start:
            params["dateDebut"] = date_start
            
        if date_end:
            params["dateFin"] = date_end
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint="/search/jurisprudence",
                params=params
            )
            
            data = response.json()
            results = []
            
            for item in data.get("results", []):
                results.append({
                    'id': item.get('id'),
                    'numero': item.get('numero'),
                    'date': item.get('dateDecision'),
                    'juridiction': item.get('juridiction'),
                    'titre': item.get('titre'),
                    'resume': item.get('resume'),
                    'texte_integral': item.get('texteIntegral'),
                    'url': item.get('url'),
                    'references': item.get('references', [])
                })
            
            return results
            
        except Exception as e:
            print(f"Erreur recherche jurisprudence: {e}")
            return []
    
    def get_code_structure(self, code_name: str) -> Optional[Dict[str, Any]]:
        """
        Récupère la structure complète d'un code.
        
        Args:
            code_name: Nom du code (ex: "code_penal")
        
        Returns:
            Structure hiérarchique du code
        """
        self._rate_limit()
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint=f"/consult/code/{code_name}/structure"
            )
            
            return response.json()
            
        except Exception as e:
            print(f"Erreur récupération structure: {e}")
            return None
    
    def get_texte_consolide(
        self,
        nature: str,
        numero: str,
        date: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère la version consolidée d'un texte.
        
        Args:
            nature: Nature du texte (LOI, DECRET, ORDONNANCE, etc.)
            numero: Numéro du texte
            date: Date de la version souhaitée (YYYY-MM-DD)
        
        Returns:
            Texte consolidé avec ses articles
        """
        self._rate_limit()
        
        params = {
            "nature": nature,
            "num": numero
        }
        
        if date:
            params["dateVersion"] = date
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint="/consult/texteConsolide",
                params=params
            )
            
            return response.json()
            
        except Exception as e:
            print(f"Erreur récupération texte consolidé: {e}")
            return None
    
    def _clean_article_text(self, text: str) -> str:
        """Nettoie le texte d'un article (supprime les balises HTML, etc.)."""
        import re
        
        # Supprimer les balises HTML
        text = re.sub(r'<[^>]+>', '', text)
        
        # Normaliser les espaces
        text = re.sub(r'\s+', ' ', text)
        
        # Supprimer les espaces en début/fin
        text = text.strip()
        
        return text
    
    def search_by_keywords(
        self,
        keywords: List[str],
        operator: str = "AND",
        code: str = None,
        in_vigueur_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Recherche par mots-clés avec opérateurs booléens.
        
        Args:
            keywords: Liste de mots-clés
            operator: "AND" ou "OR"
            code: Limiter à un code spécifique
            in_vigueur_only: Seulement les textes en vigueur
        
        Returns:
            Résultats de recherche
        """
        # Construire la requête
        if operator == "AND":
            query = " ET ".join(keywords)
        else:
            query = " OU ".join(keywords)
        
        params = {
            "q": query,
            "pageSize": 50
        }
        
        if code:
            params["fond"] = code
            
        if in_vigueur_only:
            params["etat"] = "VIGUEUR"
        
        try:
            response = self.oauth_client.make_request(
                method="GET",
                endpoint="/search/multifondsAvance",
                params=params
            )
            
            return response.json().get("results", [])
            
        except Exception as e:
            print(f"Erreur recherche mots-clés: {e}")
            return []


# Export
__all__ = ['LegifranceAPI']
