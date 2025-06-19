"""Provider Mistral pour le gestionnaire multi-LLM."""
import os
import time
import asyncio
from typing import Dict, Any, Optional
from mistralai.async_client import MistralAsyncClient
from mistralai.models.chat_completion import ChatMessage

from ..base_llm import BaseLLM


class MistralLLM(BaseLLM):
    """Provider pour les modèles Mistral."""
    
    def __init__(self, model_name: str = "mistral-large-latest"):
        """
        Initialise le provider Mistral.
        
        Args:
            model_name: Le modèle à utiliser
        """
        super().__init__(model_name)
        
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY non configurée")
        
        self.client = MistralAsyncClient(api_key=api_key)
        
        # Configuration des coûts
        self.token_costs = {
            'mistral-large-latest': {
                'input': 0.008,
                'output': 0.024
            },
            'mistral-medium-latest': {
                'input': 0.0027,
                'output': 0.0081
            },
            'mistral-small-latest': {
                'input': 0.002,
                'output': 0.006
            }
        }
    
    async def query(
        self,
        prompt: str,
        context: str = "",
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Interroge Mistral."""
        start_time = time.time()
        
        try:
            messages = [
                ChatMessage(
                    role="system",
                    content="Tu es un assistant juridique expert en droit pénal des affaires français."
                ),
                ChatMessage(
                    role="user",
                    content=f"{context}\n\n{prompt}" if context else prompt
                )
            ]
            
            response = await self.client.chat(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            
            return {
                'model': self.model_name,
                'content': content,
                'tokens_used': tokens,
                'cost': self._calculate_cost(
                    response.usage.prompt_tokens if response.usage else 0,
                    response.usage.completion_tokens if response.usage else 0
                ),
                'time': time.time() - start_time,
                'error': False
            }
            
        except Exception as e:
            return {
                'model': self.model_name,
                'content': f"Erreur: {str(e)}",
                'error': True,
                'error_message': str(e),
                'time': time.time() - start_time
            }
