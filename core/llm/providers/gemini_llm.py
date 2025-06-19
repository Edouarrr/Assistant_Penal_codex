""Provider Google Gemini pour le gestionnaire multi-LLM."""
import os
import time
import asyncio
from typing import Dict, Any, Optional
import google.generativeai as genai

from ..base_llm import BaseLLM


class GeminiLLM(BaseLLM):
    """Provider pour Google Gemini."""
    
    def __init__(self, model_name: str = "gemini-pro"):
        """
        Initialise le provider Gemini.
        
        Args:
            model_name: Le modèle à utiliser
        """
        super().__init__(model_name)
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY non configurée")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        
        # Coûts approximatifs
        self.token_costs = {
            'gemini-pro': {
                'input': 0.00025,  # $0.25 per million tokens
                'output': 0.00125  # $1.25 per million tokens
            },
            'gemini-pro-vision': {
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
        """Interroge Gemini."""
        start_time = time.time()
        
        try:
            # Configuration de la génération
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Préparer le prompt
            full_prompt = f"""Tu es un assistant juridique expert en droit pénal des affaires français.
            
{context}

{prompt}"""
            
            # Génération asynchrone
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config=generation_config
            )
            
            content = response.text
            
            # Estimation des tokens (Gemini ne retourne pas toujours le compte)
            estimated_tokens = len(full_prompt.split()) + len(content.split())
            
            return {
                'model': self.model_name,
                'content': content,
                'tokens_used': estimated_tokens,
                'cost': self._calculate_cost(
                    int(estimated_tokens * 0.4),  # Estimation input
                    int(estimated_tokens * 0.6)   # Estimation output
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
