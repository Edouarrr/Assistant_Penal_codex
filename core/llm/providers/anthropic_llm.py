"""Provider Anthropic pour le gestionnaire multi-LLM."""
import os
import time
import asyncio
from typing import Dict, Any, Optional
from anthropic import Anthropic

from ..base_llm import BaseLLM


class AnthropicLLM(BaseLLM):
    """Provider pour Claude d'Anthropic."""
    
    def __init__(self, model_name: str = "claude-3-opus-20240229"):
        """
        Initialise le provider Anthropic.
        
        Args:
            model_name: Le modèle à utiliser (claude-3-opus, claude-3-sonnet, etc.)
        """
        super().__init__(model_name)
        
        # Vérifier la clé API
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY non configurée")
        
        # Initialiser le client
        self.client = Anthropic(api_key=api_key)
        
        # Configuration des coûts (prix approximatifs)
        self.token_costs = {
            'claude-3-opus-20240229': {
                'input': 0.015,   # par 1k tokens
                'output': 0.075   # par 1k tokens
            },
            'claude-3-sonnet-20240229': {
                'input': 0.003,
                'output': 0.015
            },
            'claude-3-haiku-20240307': {
                'input': 0.00025,
                'output': 0.00125
            }
        }
    
    async def query(
        self, 
        prompt: str, 
        context: str = "",
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Interroge Claude avec le prompt donné.
        
        Args:
            prompt: La question ou instruction
            context: Le contexte (documents, etc.)
            max_tokens: Nombre maximum de tokens pour la réponse
            temperature: Créativité de la réponse (0-1)
        
        Returns:
            Dict contenant la réponse et les métadonnées
        """
        start_time = time.time()
        
        try:
            # Construire le message complet
            if context:
                full_prompt = f"""Contexte:\n{context}\n\nQuestion:\n{prompt}"""
            else:
                full_prompt = prompt
            
            # Appel à l'API Claude
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ]
            )
            
            # Extraire la réponse
            content = response.content[0].text if response.content else ""
            
            # Calculer les tokens utilisés
            # Note: Claude ne retourne pas toujours le compte exact de tokens
            # On fait une estimation basée sur la longueur du texte
            estimated_input_tokens = len(full_prompt) // 4
            estimated_output_tokens = len(content) // 4
            total_tokens = estimated_input_tokens + estimated_output_tokens
            
            # Calculer le coût
            cost = self._calculate_cost(
                estimated_input_tokens, 
                estimated_output_tokens
            )
            
            # Temps d'exécution
            execution_time = time.time() - start_time
            
            return {
                'model': self.model_name,
                'content': content,
                'tokens_used': total_tokens,
                'input_tokens': estimated_input_tokens,
                'output_tokens': estimated_output_tokens,
                'cost': cost,
                'time': execution_time,
                'error': False
            }
            
        except Exception as e:
            return {
                'model': self.model_name,
                'content': f"Erreur lors de l'appel à Claude: {str(e)}",
                'tokens_used': 0,
                'cost': 0,
                'time': time.time() - start_time,
                'error': True,
                'error_message': str(e)
            }
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calcule le coût estimé de la requête.
        
        Args:
            input_tokens: Nombre de tokens en entrée
            output_tokens: Nombre de tokens en sortie
        
        Returns:
            Coût estimé en euros
        """
        costs = self.token_costs.get(self.model_name, self.token_costs['claude-3-opus-20240229'])
        
        input_cost = (input_tokens / 1000) * costs['input']
        output_cost = (output_tokens / 1000) * costs['output']
        
        # Convertir de USD en EUR (taux approximatif)
        usd_to_eur = 0.92
        total_cost = (input_cost + output_cost) * usd_to_eur
        
        return round(total_cost, 4)
    
    def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Valide la réponse reçue de Claude.
        
        Args:
            response: La réponse à valider
        
        Returns:
            True si la réponse est valide, False sinon
        """
        if response.get('error'):
            return False
        
        content = response.get('content', '')
        if not content or len(content) < 10:
            return False
        
        # Vérifier que ce n'est pas un message d'erreur
        error_indicators = [
            "error",
            "failed",
            "unable to process",
            "something went wrong"
        ]
        
        content_lower = content.lower()
        for indicator in error_indicators:
            if indicator in content_lower:
                return False
        
        return True
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Retourne des informations sur le modèle.
        
        Returns:
            Dict avec les informations du modèle
        """
        return {
            'name': self.model_name,
            'provider': 'Anthropic',
            'capabilities': [
                'Analyse juridique approfondie',
                'Rédaction de documents légaux',
                'Détection de contradictions',
                'Synthèse de dossiers volumineux',
                'Raisonnement complexe'
            ],
            'max_tokens': 100000,  # Claude 3 peut gérer jusqu'à 100k tokens
            'supports_streaming': True,
            'supports_function_calling': False,
            'cost_per_1k_tokens': self.token_costs.get(
                self.model_name, 
                self.token_costs['claude-3-opus-20240229']
            )
        }


# Export
__all__ = ['AnthropicLLM']
