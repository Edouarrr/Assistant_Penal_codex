"""Classe de base pour tous les providers LLM."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio
import time


class BaseLLM(ABC):
    """Classe abstraite de base pour tous les providers LLM."""
    
    def __init__(self, model_name: str):
        """
        Initialise le provider LLM.
        
        Args:
            model_name: Le nom du modèle à utiliser
        """
        self.model_name = model_name
        self.token_costs = {}  # À définir dans chaque sous-classe
    
    @abstractmethod
    async def query(
        self, 
        prompt: str, 
        context: str = "",
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Méthode abstraite pour interroger le LLM.
        
        Args:
            prompt: La question ou instruction
            context: Le contexte (documents, etc.)
            max_tokens: Nombre maximum de tokens pour la réponse
            temperature: Créativité de la réponse (0-1)
        
        Returns:
            Dict contenant la réponse et les métadonnées
        """
        pass
    
    @abstractmethod
    def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Valide la réponse reçue du LLM.
        
        Args:
            response: La réponse à valider
        
        Returns:
            True si la réponse est valide, False sinon
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Retourne des informations sur le modèle.
        
        Returns:
            Dict avec les informations du modèle
        """
        pass
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estime le nombre de tokens dans un texte.
        
        Args:
            text: Le texte à analyser
        
        Returns:
            Estimation du nombre de tokens
        """
        # Estimation simple : ~1 token pour 4 caractères
        return len(text) // 4
    
    def estimate_cost(self, prompt: str, expected_output_length: int = 500) -> float:
        """
        Estime le coût d'une requête avant exécution.
        
        Args:
            prompt: Le prompt à envoyer
            expected_output_length: Longueur attendue de la réponse
        
        Returns:
            Coût estimé en euros
        """
        input_tokens = self.estimate_tokens(prompt)
        output_tokens = expected_output_length // 4
        
        costs = self.token_costs.get(self.model_name, {'input': 0.01, 'output': 0.03})
        total_cost = (input_tokens * costs.get('input', 0.01) + 
                     output_tokens * costs.get('output', 0.03)) / 1000
        
        return round(total_cost, 4)


class MockLLM(BaseLLM):
    """Provider LLM simulé pour les tests et démos."""
    
    def __init__(self, model_name: str = "mock-model"):
        """Initialise le provider mock."""
        super().__init__(model_name)
        self.token_costs = {
            'input': 0.0001,
            'output': 0.0002
        }
    
    async def query(
        self, 
        prompt: str, 
        context: str = "",
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Simule une requête LLM.
        
        Returns:
            Réponse simulée
        """
        # Simuler un délai
        await asyncio.sleep(1)
        
        # Générer une réponse simulée
        mock_response = f"""Réponse simulée du modèle {self.model_name}.

Analyse de la requête : "{prompt[:50]}..."

Points clés identifiés :
1. Aspect procédural à examiner
2. Implications juridiques potentielles
3. Recommandations stratégiques

Cette réponse est générée en mode simulation pour démonstration."""
        
        return {
            'model': self.model_name,
            'content': mock_response,
            'tokens_used': 250,
            'input_tokens': 100,
            'output_tokens': 150,
            'cost': 0.0001,
            'time': 1.0,
            'error': False
        }
    
    def validate_response(self, response: Dict[str, Any]) -> bool:
        """Valide toujours True pour le mock."""
        return not response.get('error', False)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Retourne les infos du modèle mock."""
        return {
            'name': self.model_name,
            'provider': 'Mock',
            'capabilities': ['Test', 'Démonstration'],
            'max_tokens': 4000,
            'supports_streaming': False,
            'supports_function_calling': False,
            'cost_per_1k_tokens': self.token_costs
        }


# Export
__all__ = ['BaseLLM', 'MockLLM']
