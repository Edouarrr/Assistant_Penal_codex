# core/llm/multi_llm_manager.py - VERSION MISE À JOUR
"""Gestionnaire pour interroger plusieurs LLM et fusionner les réponses."""
import asyncio
from typing import Dict, List, Any, Optional
import streamlit as st
from datetime import datetime
import json

from .base_llm import BaseLLM, MockLLM
from .providers.openai_llm import OpenAILLM
from .providers.anthropic_llm import AnthropicLLM
from .providers.mistral_llm import MistralLLM
from .providers.gemini_llm import GeminiLLM
from .providers.deepseek_llm import DeepSeekLLM
from .providers.perplexity_llm import PerplexityLLM


class MultiLLMManager:
    """Orchestre les requêtes multi-LLM et la fusion des réponses."""
    
    def __init__(self):
        """Initialise le gestionnaire multi-LLM."""
        self.providers = self._initialize_providers()
        self.fusion_strategies = {
            'synthétique': self._synthetic_fusion,
            'comparatif': self._comparative_fusion,
            'contradictoire': self._contradiction_fusion,
            'exhaustif': self._exhaustive_fusion,
            'argumentatif': self._argumentative_fusion
        }
    
    def _initialize_providers(self) -> Dict[str, BaseLLM]:
        """Initialise les providers disponibles."""
        providers = {}
        
        # OpenAI
        try:
            providers['GPT-4o'] = OpenAILLM(model_name="gpt-4o")
            providers['GPT-3.5'] = OpenAILLM(model_name="gpt-3.5-turbo")
        except Exception as e:
            st.warning(f"⚠️ OpenAI non configuré : {e}")
            providers['GPT-4o'] = MockLLM()
            providers['GPT-3.5'] = MockLLM()
        
        # Anthropic
        try:
            providers['Claude Opus 4'] = AnthropicLLM(model_name="claude-3-opus-20240229")
        except Exception as e:
            st.warning(f"⚠️ Anthropic non configuré : {e}")
            providers['Claude Opus 4'] = MockLLM()
        
        # Mistral
        try:
            providers['Mistral'] = MistralLLM(model_name="mistral-large-latest")
        except Exception as e:
            providers['Mistral'] = MockLLM()
        
        # Gemini
        try:
            providers['Gemini'] = GeminiLLM(model_name="gemini-pro")
        except Exception as e:
            providers['Gemini'] = MockLLM()
        
        # DeepSeek
        try:
            providers['DeepSeek'] = DeepSeekLLM(model_name="deepseek-chat")
        except Exception as e:
            providers['DeepSeek'] = MockLLM()
        
        # Perplexity (avec recherche web)
        try:
            providers['Perplexity'] = PerplexityLLM(model_name="pplx-70b-online")
        except Exception as e:
            providers['Perplexity'] = MockLLM()
        
        return providers
    
    def get_available_models(self) -> List[str]:
        """Retourne la liste des modèles disponibles."""
        available = []
        for name, provider in self.providers.items():
            if not isinstance(provider, MockLLM):
                available.append(name)
        return available
    
    def get_model_capabilities(self, model_name: str) -> Dict[str, Any]:
        """Retourne les capacités spéciales d'un modèle."""
        capabilities = {
            'GPT-4o': {
                'max_tokens': 128000,
                'vision': True,
                'functions': True,
                'cost_level': 'high'
            },
            'GPT-3.5': {
                'max_tokens': 16000,
                'vision': False,
                'functions': True,
                'cost_level': 'low'
            },
            'Claude Opus 4': {
                'max_tokens': 200000,
                'vision': True,
                'functions': False,
                'cost_level': 'high'
            },
            'Mistral': {
                'max_tokens': 32000,
                'vision': False,
                'functions': True,
                'cost_level': 'medium'
            },
            'Gemini': {
                'max_tokens': 32000,
                'vision': True,
                'functions': False,
                'cost_level': 'low'
            },
            'DeepSeek': {
                'max_tokens': 32000,
                'vision': False,
                'functions': False,
                'cost_level': 'very_low'
            },
            'Perplexity': {
                'max_tokens': 4000,
                'vision': False,
                'functions': False,
                'web_search': True,
                'cost_level': 'medium'
            }
        }
        return capabilities.get(model_name, {})
    
    async def query_multiple(
        self,
        prompt: str,
        context: str,
        selected_models: List[str],
        progress_callback=None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Interroge plusieurs modèles en parallèle.
        
        Args:
            prompt: La requête
            context: Le contexte (documents, etc.)
            selected_models: Liste des modèles à interroger
            progress_callback: Fonction de callback pour la progression
            temperature: Créativité (0-1)
            max_tokens: Tokens maximum par réponse
        
        Returns:
            Dict avec les réponses et métadonnées
        """
        # Filtrer les modèles disponibles
        available_models = [m for m in selected_models if m in self.providers]
        
        if not available_models:
            return {
                'error': 'Aucun modèle disponible',
                'responses': {},
                'metadata': {}
            }
        
        # Créer les tâches asynchrones
        tasks = []
        for model_name in available_models:
            provider = self.providers[model_name]
            task = provider.query(prompt, context, max_tokens, temperature)
            tasks.append((model_name, task))
        
        # Exécuter en parallèle
        responses = {}
        total_cost = 0
        total_tokens = 0
        
        for i, (model_name, task) in enumerate(tasks):
            if progress_callback:
                progress_callback(i / len(tasks), f"Interrogation de {model_name}...")
            
            try:
                result = await task
                responses[model_name] = result
                
                # Calculer les métriques
                if not result.get('error', False):
                    total_cost += result.get('cost', 0)
                    total_tokens += result.get('tokens_used', 0)
                    
            except Exception as e:
                responses[model_name] = {
                    'error': True,
                    'content': f"Erreur: {str(e)}",
                    'error_message': str(e)
                }
        
        if progress_callback:
            progress_callback(1.0, "Terminé")
        
        return {
            'responses': responses,
            'metadata': {
                'total_cost': total_cost,
                'total_tokens': total_tokens,
                'models_used': len(responses),
                'timestamp': datetime.now().isoformat()
            }
        }
    
    def fuse_responses(
        self,
        responses: Dict[str, Dict[str, Any]],
        strategy: str = 'synthétique',
        options: Dict[str, Any] = None
    ) -> str:
        """
        Fusionne les réponses selon la stratégie choisie.
        
        Args:
            responses: Dict des réponses par modèle
            strategy: Stratégie de fusion
            options: Options supplémentaires
        
        Returns:
            Texte fusionné
        """
        # Filtrer les réponses valides
        valid_responses = {
            model: resp for model, resp in responses.items()
            if not resp.get('error', False)
        }
        
        if not valid_responses:
            return "❌ Aucune réponse valide obtenue des modèles."
        
        # Appliquer la stratégie
        fusion_func = self.fusion_strategies.get(
            strategy,
            self._synthetic_fusion
        )
        
        return fusion_func(valid_responses, options or {})
    
    def _synthetic_fusion(
        self,
        responses: Dict[str, Dict[str, Any]],
        options: Dict[str, Any]
    ) -> str:
        """Fusion synthétique : combine les meilleures parties."""
        sections = []
        
        # Extraire les points clés de chaque réponse
        all_points = []
        for model, resp in responses.items():
            content = resp.get('content', '')
            # Extraire les points principaux (simple heuristique)
            points = [p.strip() for p in content.split('\n') if p.strip() and len(p.strip()) > 20]
            all_points.extend(points[:5])  # Max 5 points par modèle
        
        # Dédupliquer et organiser
        unique_points = list(dict.fromkeys(all_points))
        
        # Construire la synthèse
        synthesis = "## Synthèse des analyses\n\n"
        
        # Points de convergence
        synthesis += "### Points de convergence\n"
        for point in unique_points[:10]:
            synthesis += f"- {point}\n"
        
        # Ajout des spécificités si pertinent
        if len(responses) > 1:
            synthesis += "\n### Éléments complémentaires par modèle\n"
            for model, resp in responses.items():
                synthesis += f"\n**{model}** : "
                # Extraire un élément unique
                content = resp.get('content', '')[:200]
                synthesis += f"{content}...\n"
        
        return synthesis
    
    def _comparative_fusion(
        self,
        responses: Dict[str, Dict[str, Any]],
        options: Dict[str, Any]
    ) -> str:
        """Fusion comparative : met en parallèle les réponses."""
        comparison = "## Analyse comparative des réponses\n\n"
        
        # Tableau comparatif
        comparison += "| Modèle | Analyse | Points clés |\n"
        comparison += "|--------|---------|-------------|\n"
        
        for model, resp in responses.items():
            content = resp.get('content', '')
            # Résumer en 100 mots
            summary = content[:200] + "..." if len(content) > 200 else content
            summary = summary.replace('\n', ' ')
            
            # Extraire 3 points clés
            lines = content.split('\n')
            key_points = [l.strip() for l in lines if l.strip() and len(l.strip()) > 10][:3]
            key_points_str = "<br>".join([f"• {p[:50]}..." for p in key_points])
            
            comparison += f"| **{model}** | {summary} | {key_points_str} |\n"
        
        # Méta-analyse
        comparison += "\n### Méta-analyse\n"
        comparison += f"- **Nombre de modèles consultés** : {len(responses)}\n"
        comparison += f"- **Consensus** : {'Élevé' if len(responses) > 2 else 'À vérifier'}\n"
        
        return comparison
    
    def _contradiction_fusion(
        self,
        responses: Dict[str, Dict[str, Any]],
        options: Dict[str, Any]
    ) -> str:
        """Fusion contradictoire : met en évidence les désaccords."""
        analysis = "## Analyse des divergences\n\n"
        
        # Identifier les contradictions potentielles
        # (Implémentation simplifiée - en production, utiliser NLP)
        
        analysis += "### Points de divergence identifiés\n\n"
        
        # Comparer les réponses deux à deux
        models = list(responses.keys())
        for i in range(len(models)):
            for j in range(i + 1, len(models)):
                model1, model2 = models[i], models[j]
                content1 = responses[model1].get('content', '')
                content2 = responses[model2].get('content', '')
                
                # Recherche simple de termes opposés
                if ('oui' in content1.lower() and 'non' in content2.lower()) or \
                   ('non' in content1.lower() and 'oui' in content2.lower()):
                    analysis += f"⚠️ **Divergence entre {model1} et {model2}** sur une réponse binaire\n"
                
                # Vérifier les nombres différents
                import re
                numbers1 = set(re.findall(r'\d+', content1))
                numbers2 = set(re.findall(r'\d+', content2))
                if numbers1 and numbers2 and numbers1 != numbers2:
                    analysis += f"⚠️ **Divergence numérique entre {model1} et {model2}**\n"
        
        # Recommandation
        analysis += "\n### Recommandation\n"
        analysis += "Face aux divergences identifiées, il est recommandé de :\n"
        analysis += "1. Vérifier les sources primaires\n"
        analysis += "2. Demander des clarifications supplémentaires\n"
        analysis += "3. Consulter un expert humain pour trancher\n"
        
        return analysis
    
    def _exhaustive_fusion(
        self,
        responses: Dict[str, Dict[str, Any]],
        options: Dict[str, Any]
    ) -> str:
        """Fusion exhaustive : compile toutes les informations."""
        compilation = "## Compilation exhaustive des analyses\n\n"
        
        # Introduction
        compilation += f"*Synthèse basée sur {len(responses)} modèles d'IA*\n\n"
        
        # Compiler toutes les réponses
        for model, resp in responses.items():
            compilation += f"### {model}\n"
            compilation += f"*Temps de réponse : {resp.get('time', 0):.2f}s | "
            compilation += f"Tokens : {resp.get('tokens_used', 0)}*\n\n"
            
            content = resp.get('content', '')
            compilation += content
            compilation += "\n\n---\n\n"
        
        # Résumé des métriques
        total_tokens = sum(r.get('tokens_used', 0) for r in responses.values())
        total_cost = sum(r.get('cost', 0) for r in responses.values())
        
        compilation += "### Métriques globales\n"
        compilation += f"- **Tokens totaux** : {total_tokens}\n"
        compilation += f"- **Coût estimé** : {total_cost:.4f}$\n"
        compilation += f"- **Modèles utilisés** : {', '.join(responses.keys())}\n"
        
        return compilation
    
    def _argumentative_fusion(
        self,
        responses: Dict[str, Dict[str, Any]],
        options: Dict[str, Any]
    ) -> str:
        """Fusion argumentative : structure les arguments de manière juridique."""
        argumentation = "## Argumentation juridique consolidée\n\n"
        
        # Extraire et catégoriser les arguments
        arguments_pour = []
        arguments_contre = []
        faits = []
        precedents = []
        
        for model, resp in responses.items():
            content = resp.get('content', '').lower()
            lines = resp.get('content', '').split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Catégorisation simple
                if any(word in line.lower() for word in ['favorable', 'avantage', 'pour', 'positif']):
                    arguments_pour.append((model, line))
                elif any(word in line.lower() for word in ['défavorable', 'contre', 'risque', 'négatif']):
                    arguments_contre.append((model, line))
                elif any(word in line.lower() for word in ['fait', 'constat', 'établi', 'prouvé']):
                    faits.append((model, line))
                elif any(word in line.lower() for word in ['jurisprudence', 'arrêt', 'décision', 'cass']):
                    precedents.append((model, line))
        
        # Structurer l'argumentation
        argumentation += "### I. Faits établis\n"
        for model, fait in faits[:5]:
            argumentation += f"- {fait} *[{model}]*\n"
        
        argumentation += "\n### II. Arguments favorables\n"
        for model, arg in arguments_pour[:5]:
            argumentation += f"- {arg} *[{model}]*\n"
        
        argumentation += "\n### III. Arguments défavorables\n"
        for model, arg in arguments_contre[:5]:
            argumentation += f"- {arg} *[{model}]*\n"
        
        argumentation += "\n### IV. Jurisprudence pertinente\n"
        for model, prec in precedents[:3]:
            argumentation += f"- {prec} *[{model}]*\n"
        
        argumentation += "\n### V. Conclusion\n"
        argumentation += "Au regard des éléments analysés par l'ensemble des modèles, "
        
        # Déterminer la tendance
        if len(arguments_pour) > len(arguments_contre):
            argumentation += "la position apparaît **favorable**."
        elif len(arguments_contre) > len(arguments_pour):
            argumentation += "la position présente des **risques significatifs**."
        else:
            argumentation += "la situation nécessite une **analyse approfondie** au cas par cas."
        
        return argumentation
    
    async def estimate_cost(
        self,
        prompt: str,
        context: str,
        selected_models: List[str]
    ) -> Dict[str, float]:
        """
        Estime le coût avant exécution.
        
        Returns:
            Dict avec coût par modèle et total
        """
        costs = {}
        total_cost = 0
        
        # Estimation basique : compter les tokens
        total_text = prompt + context
        estimated_tokens = len(total_text.split()) * 1.3  # Facteur de conversion
        
        for model in selected_models:
            if model in self.providers:
                provider = self.providers[model]
                
                # Récupérer les coûts du provider
                if hasattr(provider, 'token_costs'):
                    model_costs = provider.token_costs.get(
                        provider.model_name,
                        {'input': 0.001, 'output': 0.002}
                    )
                    
                    # Estimation : 50% input, 50% output
                    input_cost = (estimated_tokens * 0.5 / 1000) * model_costs['input']
                    output_cost = (estimated_tokens * 0.5 / 1000) * model_costs['output']
                    
                    model_cost = input_cost + output_cost
                    costs[model] = model_cost
                    total_cost += model_cost
        
        costs['total'] = total_cost
        return costs


# Export
__all__ = ['MultiLLMManager']
