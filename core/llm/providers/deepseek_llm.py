"""Provider DeepSeek pour le gestionnaire multi-LLM."""
import os
import time
import asyncio
from typing import Dict, Any, Optional
from openai import AsyncOpenAI

from ..base_llm import BaseLLM


class DeepSeekLLM(BaseLLM):
    """Provider pour DeepSeek (utilise l'API compatible OpenAI)."""
    
    def __init__(self, model_name: str = "deepseek-chat"):
        """
        Initialise le provider DeepSeek.
        
        Args:
            model_name: Le modèle à utiliser
        """
        super().__init__(model_name)
        
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY non configurée")
        
        # DeepSeek utilise une API compatible OpenAI
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        
        # Configuration des coûts (très compétitifs)
        self.token_costs = {
            'deepseek-chat': {
                'input': 0.00014,   # $0.14 per million tokens
                'output': 0.00028   # $0.28 per million tokens
            },
            'deepseek-coder': {
                'input': 0.00014,
                'output': 0.00028
            }
        }
    
    async def query(
        self,
        prompt: str,
        context: str = "",
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Interroge DeepSeek."""
        start_time = time.time()
        
        try:
            messages = [
                {
                    "role": "system",
                    "content": "Tu es un assistant juridique expert en droit pénal des affaires français. "
                              "Tu fournis des analyses précises et détaillées."
                },
                {
                    "role": "user",
                    "content": f"{context}\n\n{prompt}" if context else prompt
                }
            ]
            
            response = await self.client.chat.completions.create(
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
