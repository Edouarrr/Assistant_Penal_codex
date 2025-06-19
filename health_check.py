"""
health_check.py - Vérification de santé intégrée à l'application
S'exécute automatiquement au démarrage de Streamlit sur Railway
"""
import os
import sys
from pathlib import Path
import streamlit as st
from typing import Dict, List, Tuple
import importlib.util
import yaml


class HealthChecker:
    """Vérifie l'état de l'application au démarrage."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.success = []
    
    def check_all(self) -> Tuple[bool, Dict[str, List[str]]]:
        """Effectue toutes les vérifications."""
        # 1. Créer les dossiers manquants
        self._ensure_directories()
        
        # 2. Créer les fichiers de config par défaut
        self._ensure_config_files()
        
        # 3. Vérifier les modules Python
        self._check_modules()
        
        # 4. Vérifier les variables d'environnement
        self._check_environment()
        
        # 5. Créer les __init__.py manquants
        self._ensure_init_files()
        
        return len(self.issues) == 0, {
            'issues': self.issues,
            'warnings': self.warnings,
            'success': self.success
        }
    
    def _ensure_directories(self):
        """Crée automatiquement les dossiers nécessaires."""
        required_dirs = [
            'data/vector_db',
            'logs',
            'templates/actes',
            'templates/lettres',
            'static',
            'config',
            'raw_documents',
            'ocr_output',
            'summaries',
            'pieces_communiquees'
        ]
        
        for dir_path in required_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        self.success.append("✅ Structure des dossiers créée")
    
    def _ensure_config_files(self):
        """Crée les fichiers de configuration par défaut s'ils n'existent pas."""
        # Configuration utilisateurs par défaut
        users_path = Path('config/users.yaml')
        if not users_path.exists():
            default_users = {
                'credentials': {
                    'usernames': {
                        'admin': {
                            'name': 'Administrateur',
                            'password': 'steru2024',
                            'role': 'admin',
                            'email': 'admin@steru-baratte.com'
                        },
                        'demo': {
                            'name': 'Utilisateur Demo',
                            'password': 'demo2024',
                            'role': 'collaborateur',
                            'email': 'demo@steru-baratte.com'
                        }
                    }
                },
                'security': {
                    'password_min_length': 8,
                    'session_timeout_minutes': 480,
                    'max_login_attempts': 5
                }
            }
            
            users_path.parent.mkdir(exist_ok=True)
            with open(users_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_users, f, allow_unicode=True)
            
            self.warnings.append("⚠️  Fichier config/users.yaml créé avec config par défaut")
        
        # Configuration vectorisation par défaut
        vector_path = Path('config/vector_settings.yaml')
        if not vector_path.exists():
            default_vector = {
                'vectorization': {
                    'chunk_size': 800,
                    'chunk_overlap': 100,
                    'model': 'text-embedding-ada-002',
                    'persist_directory': 'data/vector_db',
                    'log_path': 'logs/vector.log'
                }
            }
            
            with open(vector_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_vector, f, allow_unicode=True)
            
            self.success.append("✅ Configuration de vectorisation créée")
    
    def _check_modules(self):
        """Vérifie la présence des modules essentiels."""
        essential_modules = [
            'streamlit',
            'openai',
            'langchain',
            'chromadb',
            'PyPDF2',
            'msal'
        ]
        
        missing = []
        for module in essential_modules:
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        
        if missing:
            self.issues.append(f"❌ Modules Python manquants : {', '.join(missing)}")
        else:
            self.success.append("✅ Tous les modules essentiels sont installés")
    
    def _check_environment(self):
        """Vérifie les variables d'environnement."""
        # Au moins une API doit être configurée
        api_keys = [
            'OPENAI_API_KEY',
            'ANTHROPIC_API_KEY',
            'MISTRAL_API_KEY',
            'GEMINI_API_KEY'
        ]
        
        has_api = any(os.getenv(key) for key in api_keys)
        
        if not has_api:
            self.warnings.append(
                "⚠️  Aucune API IA configurée - Mode démo activé\n"
                "   Configurez au moins une clé API dans Railway"
            )
        else:
            configured_apis = [key for key in api_keys if os.getenv(key)]
            self.success.append(f"✅ APIs configurées : {', '.join(configured_apis)}")
        
        # Vérifier SharePoint (optionnel)
        sharepoint_vars = [
            'SHAREPOINT_CLIENT_ID',
            'SHAREPOINT_CLIENT_SECRET',
            'SHAREPOINT_TENANT_ID'
        ]
        
        has_sharepoint = all(os.getenv(var) for var in sharepoint_vars)
        if has_sharepoint:
            self.success.append("✅ SharePoint configuré")
        else:
            self.warnings.append("⚠️  SharePoint non configuré (optionnel)")
    
    def _ensure_init_files(self):
        """Crée les fichiers __init__.py manquants."""
        init_locations = [
            'core',
            'core/llm',
            'core/llm/providers',
            'core/juridique',
            'core/analysis',
            'core/search',
            'core/generation',
            'core/security',
            'core/auth',
            'ui',
            'ui/pages'
        ]
        
        for location in init_locations:
            init_path = Path(location) / '__init__.py'
            if not init_path.exists():
                init_path.parent.mkdir(parents=True, exist_ok=True)
                init_path.touch()
        
        self.success.append("✅ Fichiers __init__.py créés")


def display_health_status():
    """Affiche l'état de santé dans Streamlit."""
    if 'health_checked' not in st.session_state:
        checker = HealthChecker()
        is_healthy, report = checker.check_all()
        
        st.session_state.health_checked = True
        st.session_state.health_report = report
        st.session_state.is_healthy = is_healthy
        
        # Afficher seulement s'il y a des problèmes
        if not is_healthy or report['warnings']:
            with st.sidebar:
                with st.expander("🏥 État de santé", expanded=not is_healthy):
                    if report['issues']:
                        st.error("**Problèmes critiques :**")
                        for issue in report['issues']:
                            st.write(issue)
                    
                    if report['warnings']:
                        st.warning("**Avertissements :**")
                        for warning in report['warnings']:
                            st.write(warning)
                    
                    if report['success']:
                        st.success("**Éléments OK :**")
                        for success in report['success'][:3]:
                            st.write(success)
                        if len(report['success']) > 3:
                            st.caption(f"... et {len(report['success']) - 3} autres")
                    
                    if not is_healthy:
                        st.error("⚠️ L'application peut ne pas fonctionner correctement")
                        st.info("Vérifiez la configuration dans Railway")


# Fonction à appeler au début de streamlit_app.py
def ensure_app_health():
    """Vérifie et corrige l'état de l'application au démarrage."""
    # Exécuter en silence au démarrage
    checker = HealthChecker()
    is_healthy, report = checker.check_all()
    
    # Logger les problèmes
    if not is_healthy:
        print("⚠️  PROBLÈMES DÉTECTÉS AU DÉMARRAGE:")
        for issue in report['issues']:
            print(f"   {issue}")
    
    # Retourner l'état
    return is_healthy, report


# Export
__all__ = ['HealthChecker', 'display_health_status', 'ensure_app_health']
