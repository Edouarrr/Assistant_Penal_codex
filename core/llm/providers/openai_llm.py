"""Provider OpenAI pour le gestionnaire multi-LLM."""
import os
import time
import asyncio
from typing import Dict, Any, Optional
import openai
from openai import AsyncOpenAI

from ..base_llm import BaseLLM


class OpenAILLM(BaseLLM):
    """Provider pour les modèles OpenAI (GPT-4, GPT-3.5, etc.)."""
    
    def __init__(self, model_name: str = "gpt-4o"):
        """
        Initialise le provider OpenAI.
        
        Args:
            model_name: Le modèle à utiliser (gpt-4o, gpt-3.5-turbo, etc.)
        """
        super().__init__(model_name)
        
        # Vérifier la clé API
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY non configurée")
        
        # Initialiser le client asynchrone
        self.client = AsyncOpenAI(api_key=api_key)
        
        # Configuration des coûts (prix en USD par 1k tokens)
        self.token_costs = {
            'gpt-4o': {
                'input': 0.005,    # $5 par million de tokens
                'output': 0.015    # $15 par million de tokens
            },
            'gpt-4o-mini': {
                'input': 0.00015,
                'output': 0.0006
            },
            'gpt-4-turbo': {
                'input': 0.01,
                'output': 0.03
            },
            'gpt-3.5-turbo': {
                'input': 0.0005,
                'output': 0.0015
            },
            'gpt-3.5-turbo-16k': {
                'input': 0.003,
                'output': 0.004
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
        Interroge GPT avec le prompt donné.
        
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
            # Construire les messages
            messages = []
            
            # Message système pour configurer le comportement
            messages.append({
                "role": "system",
                "content": "Tu es un assistant juridique spécialisé en droit pénal des affaires. "
                          "Tu fournis des analyses précises et détaillées en citant toujours tes sources."
            })
            
            # Ajouter le contexte si présent
            if context:
                messages.append({
                    "role": "system",
                    "content": f"Contexte documentaire:\n{context}"
                })
            
            # Ajouter la question de l'utilisateur
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Appel à l'API OpenAI
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            # Extraire la réponse
            content = response.choices[0].message.content if response.choices else ""
            
            # Récupérer les statistiques d'usage
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0
            
            # Calculer le coût
            cost = self._calculate_cost(input_tokens, output_tokens)
            
            # Temps d'exécution
            execution_time = time.time() - start_time
            
            return {
                'model': self.model_name,
                'content': content,
                'tokens_used': total_tokens,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost': cost,
                'time': execution_time,
                'error': False,
                'finish_reason': response.choices[0].finish_reason if response.choices else None
            }
            
        except Exception as e:
            return {
                'model': self.model_name,
                'content': f"Erreur lors de l'appel à OpenAI: {str(e)}",
                'tokens_used': 0,
                'cost': 0,
                'time': time.time() - start_time,
                'error': True,
                'error_message': str(e)
            }
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calcule le coût de la requête.
        
        Args:
            input_tokens: Nombre de tokens en entrée
            output_tokens: Nombre de tokens en sortie
        
        Returns:
            Coût en euros
        """
        # Obtenir les coûts pour ce modèle
        costs = self.token_costs.get(self.model_name, self.token_costs['gpt-3.5-turbo'])
        
        # Calculer le coût en USD
        input_cost = (input_tokens / 1000) * costs['input']
        output_cost = (output_tokens / 1000) * costs['output']
        
        # Convertir en EUR (taux approximatif)
        usd_to_eur = 0.92
        total_cost = (input_cost + output_cost) * usd_to_eur
        
        return round(total_cost, 4)
    
    def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        Valide la réponse reçue d'OpenAI.
        
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
        
        # Vérifier le finish_reason
        finish_reason = response.get('finish_reason')
        if finish_reason and finish_reason not in ['stop', 'length']:
            return False
        
        return True
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Retourne des informations sur le modèle.
        
        Returns:
            Dict avec les informations du modèle
        """
        model_contexts = {
            'gpt-4o': 128000,
            'gpt-4o-mini': 128000,
            'gpt-4-turbo': 128000,
            'gpt-3.5-turbo': 16385,
            'gpt-3.5-turbo-16k': 16385
        }
        
        return {
            'name': self.model_name,
            'provider': 'OpenAI',
            'capabilities': [
                'Analyse juridique',
                'Rédaction de documents',
                'Extraction d\'informations',
                'Résumé de textes',
                'Questions-réponses',
                'Traduction juridique'
            ],
            'max_tokens': model_contexts.get(self.model_name, 4096),
            'supports_streaming': True,
            'supports_function_calling': True,
            'supports_vision': self.model_name in ['gpt-4o', 'gpt-4o-mini'],
            'cost_per_1k_tokens': self.token_costs.get(
                self.model_name, 
                self.token_costs['gpt-3.5-turbo']
            )
        }
    
    async def query_with_functions(
        self,
        prompt: str,
        context: str = "",
        functions: list = None,
        function_call: str = "auto"
    ) -> Dict[str, Any]:
        """
        Interroge GPT avec des fonctions (pour des tâches structurées).
        
        Args:
            prompt: La question
            context: Le contexte
            functions: Liste des fonctions disponibles
            function_call: Mode d'appel ("auto", "none", ou nom de fonction)
        
        Returns:
            Réponse avec potentiel appel de fonction
        """
        start_time = time.time()
        
        try:
            messages = [
                {"role": "system", "content": "Assistant juridique expert."},
                {"role": "user", "content": f"{context}\n\n{prompt}" if context else prompt}
            ]
            
            # Paramètres de base
            params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.3  # Plus déterministe pour les fonctions
            }
            
            # Ajouter les fonctions si fournies
            if functions:
                params["functions"] = functions
                params["function_call"] = function_call
            
            response = await self.client.chat.completions.create(**params)
            
            # Traiter la réponse
            choice = response.choices[0]
            
            if hasattr(choice.message, 'function_call') and choice.message.function_call:
                # Réponse avec appel de fonction
                return {
                    'model': self.model_name,
                    'function_call': {
                        'name': choice.message.function_call.name,
                        'arguments': choice.message.function_call.arguments
                    },
                    'content': choice.message.content or "",
                    'tokens_used': response.usage.total_tokens if response.usage else 0,
                    'cost': self._calculate_cost(
                        response.usage.prompt_tokens if response.usage else 0,
                        response.usage.completion_tokens if response.usage else 0
                    ),
                    'time': time.time() - start_time,
                    'error': False
                }
            else:
                # Réponse normale
                return {
                    'model': self.model_name,
                    'content': choice.message.content,
                    'tokens_used': response.usage.total_tokens if response.usage else 0,
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


# Export
__all__ = ['OpenAILLM']
