"""Module de gestion des LLM pour l'assistant juridique."""
from .base_llm import BaseLLM, MockLLM
from .multi_llm_manager import MultiLLMManager

__all__ = ['BaseLLM', 'MockLLM', 'MultiLLMManager']
