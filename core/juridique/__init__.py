# core/juridique/__init__.py
"""
Module d'intégration avec les APIs juridiques françaises.
Fournit un accès unifié à Legifrance et Judilibre.
"""

from .oauth_client import OAuth2Client, get_oauth_client
from .legifrance_api import LegifranceAPI
from .judilibre_api import JudilibreAPI

# Classe d'interface unifiée
class JuridiqueAPI:
    """Interface unifiée pour accéder aux APIs juridiques."""
    
    def __init__(self):
        self.legifrance = LegifranceAPI()
        self.judilibre = JudilibreAPI()
    
    def search_all(
        self,
        query: str,
        include_codes: bool = True,
        include_jurisprudence: bool = True,
        max_results_per_source: int = 10
    ) -> Dict[str, Any]:
        """
        Recherche dans toutes les sources juridiques.
        
        Args:
            query: Requête de recherche
            include_codes: Inclure la recherche dans les codes
            include_jurisprudence: Inclure la recherche dans la jurisprudence
            max_results_per_source: Nombre max de résultats par source
        
        Returns:
            Résultats combinés de toutes les sources
        """
        results = {
            'query': query,
            'timestamp': datetime.now().isoformat(),
            'sources': {}
        }
        
        # Recherche dans les codes
        if include_codes:
            try:
                code_results = self.legifrance.search_codes(
                    query=query,
                    max_results=max_results_per_source
                )
                results['sources']['codes'] = {
                    'count': len(code_results),
                    'results': code_results
                }
            except Exception as e:
                results['sources']['codes'] = {
                    'error': str(e),
                    'results': []
                }
        
        # Recherche dans la jurisprudence
        if include_jurisprudence:
            try:
                juris_results = self.judilibre.search(
                    query=query,
                    max_results=max_results_per_source
                )
                results['sources']['jurisprudence'] = {
                    'count': juris_results.get('total', 0),
                    'results': juris_results.get('results', [])
                }
            except Exception as e:
                results['sources']['jurisprudence'] = {
                    'error': str(e),
                    'results': []
                }
        
        # Total
        results['total_results'] = sum(
            source.get('count', len(source.get('results', [])))
            for source in results['sources'].values()
        )
        
        return results


# Fonction helper pour vérifier la configuration
def check_juridique_config() -> Dict[str, bool]:
    """Vérifie la configuration des APIs juridiques."""
    import os
    
    return {
        'legifrance': {
            'client_id': bool(os.getenv('LEGIFRANCE_CLIENT_ID')),
            'client_secret': bool(os.getenv('LEGIFRANCE_CLIENT_SECRET')),
            'configured': bool(os.getenv('LEGIFRANCE_CLIENT_ID') and os.getenv('LEGIFRANCE_CLIENT_SECRET'))
        },
        'judilibre': {
            'client_id': bool(os.getenv('JUDILIBRE_CLIENT_ID')),
            'client_secret': bool(os.getenv('JUDILIBRE_CLIENT_SECRET')),
            'configured': bool(os.getenv('JUDILIBRE_CLIENT_ID') and os.getenv('JUDILIBRE_CLIENT_SECRET'))
        }
    }


# Export
__all__ = [
    'OAuth2Client',
    'get_oauth_client',
    'LegifranceAPI',
    'JudilibreAPI',
    'JuridiqueAPI',
    'check_juridique_config'
]


# Import pour compatibilité
from typing import Dict, Any
from datetime import datetime
