"""
Initialisation de ChromaDB pour l'Assistant Pénal
"""
import os
from pathlib import Path
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Récupérer le path depuis l'environnement ou utiliser un défaut
CHROMA_PATH = os.getenv('CHROMA_PERSIST_DIRECTORY', '/app/data/chroma_db')

# S'assurer que le répertoire existe
try:
    Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)
    logger.info(f"✅ Répertoire ChromaDB créé/vérifié : {CHROMA_PATH}")
except Exception as e:
    logger.error(f"❌ Erreur création répertoire ChromaDB : {e}")

def get_chroma_client():
    """
    Retourne un client ChromaDB configuré avec persistence
    """
    try:
        import chromadb
        from chromadb.config import Settings
        
        client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        logger.info(f"✅ Client ChromaDB initialisé avec path : {CHROMA_PATH}")
        return client
    except Exception as e:
        logger.error(f"❌ Erreur initialisation ChromaDB : {e}")
        return None

def get_or_create_collection(collection_name="documents_juridiques"):
    """
    Récupère ou crée une collection ChromaDB
    """
    client = get_chroma_client()
    if not client:
        return None
    
    try:
        # Pour OpenAI embeddings
        from chromadb.utils import embedding_functions
        
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-ada-002"
        )
        
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
        
        logger.info(f"✅ Collection '{collection_name}' prête ({collection.count()} documents)")
        return collection
    except Exception as e:
        logger.error(f"❌ Erreur création collection : {e}")
        return None

# Export des fonctions principales
__all__ = ['CHROMA_PATH', 'get_chroma_client', 'get_or_create_collection']
