# core/auth/authentication.py
"""Module d'authentification pour l'application Assistant Pénal."""
import streamlit as st
import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple
import hashlib
import bcrypt
from datetime import datetime, timedelta
import secrets


class AuthManager:
    """Gestionnaire d'authentification avec support des sessions."""
    
    def __init__(self, config_path: str = "config/users.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._initialize_session()
    
    def _load_config(self) -> Dict:
        """Charge la configuration des utilisateurs."""
        if not self.config_path.exists():
            st.error(f"❌ Fichier de configuration introuvable : {self.config_path}")
            return {"credentials": {"usernames": {}}, "security": {}, "roles": {}}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement de la configuration : {e}")
            return {"credentials": {"usernames": {}}, "security": {}, "roles": {}}
    
    def _initialize_session(self):
        """Initialise les variables de session."""
        if 'authentication_status' not in st.session_state:
            st.session_state['authentication_status'] = None
        if 'username' not in st.session_state:
            st.session_state['username'] = None
        if 'name' not in st.session_state:
            st.session_state['name'] = None
        if 'role' not in st.session_state:
            st.session_state['role'] = None
        if 'login_attempts' not in st.session_state:
            st.session_state['login_attempts'] = 0
        if 'lockout_until' not in st.session_state:
            st.session_state['lockout_until'] = None
    
    def _hash_password(self, password: str) -> str:
        """Hash le mot de passe avec bcrypt."""
        # Pour la démo, on utilise un hash simple
        # En production, utiliser bcrypt
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Vérifie le mot de passe."""
        # Pour la démo, comparaison simple
        # En production, utiliser bcrypt.checkpw
        return self._hash_password(password) == hashed
    
    def _check_lockout(self) -> bool:
        """Vérifie si le compte est verrouillé."""
        if st.session_state.get('lockout_until'):
            if datetime.now() < st.session_state['lockout_until']:
                remaining = (st.session_state['lockout_until'] - datetime.now()).seconds // 60
                st.error(f"🔒 Compte verrouillé. Réessayez dans {remaining} minutes.")
                return True
            else:
                # Déverrouiller
                st.session_state['lockout_until'] = None
                st.session_state['login_attempts'] = 0
        return False
    
    def login(self, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Vérifie les identifiants et retourne (succès, nom_complet)."""
        # Vérifier le verrouillage
        if self._check_lockout():
            return False, None
        
        users = self.config.get("credentials", {}).get("usernames", {})
        security = self.config.get("security", {})
        
        if username not in users:
            st.session_state['login_attempts'] += 1
            return False, None
        
        user_data = users[username]
        
        # Pour la démo, on accepte le mot de passe "steru2024" pour tous
        if password == "steru2024" or password == user_data.get('password'):
            # Réinitialiser les tentatives
            st.session_state['login_attempts'] = 0
            
            # Stocker les infos utilisateur
            st.session_state['authentication_status'] = True
            st.session_state['username'] = username
            st.session_state['name'] = user_data.get('name', username)
            st.session_state['role'] = user_data.get('role', 'user')
            st.session_state['permissions'] = user_data.get('permissions', [])
            
            return True, user_data.get('name', username)
        else:
            # Incrémenter les tentatives
            st.session_state['login_attempts'] += 1
            
            # Vérifier le verrouillage
            max_attempts = security.get('max_login_attempts', 5)
            if st.session_state['login_attempts'] >= max_attempts:
                lockout_duration = security.get('lockout_duration_minutes', 30)
                st.session_state['lockout_until'] = datetime.now() + timedelta(minutes=lockout_duration)
                st.error(f"🔒 Trop de tentatives. Compte verrouillé pour {lockout_duration} minutes.")
            
            return False, None
    
    def logout(self):
        """Déconnecte l'utilisateur."""
        st.session_state['authentication_status'] = None
        st.session_state['username'] = None
        st.session_state['name'] = None
        st.session_state['role'] = None
        st.session_state['permissions'] = []
        st.rerun()
    
    def render_login_form(self) -> Optional[str]:
        """Affiche le formulaire de connexion et retourne le nom d'utilisateur si connecté."""
        # Si déjà connecté
        if st.session_state.get('authentication_status'):
            return st.session_state.get('username')
        
        # Sinon afficher le formulaire
        with st.container():
            st.markdown("### 🔐 Connexion")
            
            with st.form("login_form"):
                username = st.text_input(
                    "Nom d'utilisateur",
                    placeholder="Entrez votre identifiant",
                    key="login_username"
                )
                
                password = st.text_input(
                    "Mot de passe",
                    type="password",
                    placeholder="Entrez votre mot de passe",
                    key="login_password"
                )
                
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    submit = st.form_submit_button(
                        "Se connecter",
                        type="primary",
                        use_container_width=True
                    )
                
                with col2:
                    if st.form_submit_button("Mot de passe oublié ?"):
                        st.info("Contactez l'administrateur")
            
            if submit:
                if username and password:
                    success, name = self.login(username, password)
                    if success:
                        st.success(f"✅ Bienvenue {name} !")
                        st.rerun()
                    else:
                        if not self._check_lockout():
                            attempts_left = self.config.get('security', {}).get('max_login_attempts', 5) - st.session_state.get('login_attempts', 0)
                            if attempts_left > 0:
                                st.error(f"❌ Identifiants incorrects. {attempts_left} tentatives restantes.")
                            else:
                                st.error("❌ Identifiants incorrects.")
                else:
                    st.warning("⚠️ Veuillez remplir tous les champs")
            
            # Afficher un message d'aide
            with st.expander("ℹ️ Première connexion ?"):
                st.write("""
                **Pour les tests :**
                - Utilisateur : `admin` ou `esteru`
                - Mot de passe : `steru2024`
                
                **Important :** Changez votre mot de passe dès la première connexion !
                """)
        
        return None
    
    def check_permission(self, permission: str) -> bool:
        """Vérifie si l'utilisateur a une permission spécifique."""
        if not st.session_state.get('authentication_status'):
            return False
        
        user_permissions = st.session_state.get('permissions', [])
        user_role = st.session_state.get('role', '')
        
        # Admin a toutes les permissions
        if user_role == 'admin' or 'full_access' in user_permissions:
            return True
        
        return permission in user_permissions
    
    def require_permission(self, permission: str):
        """Décorateur pour protéger les fonctions."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if self.check_permission(permission):
                    return func(*args, **kwargs)
                else:
                    st.error("❌ Vous n'avez pas la permission d'accéder à cette fonctionnalité.")
                    return None
            return wrapper
        return decorator
    
    def get_user_info(self) -> Dict[str, Any]:
        """Retourne les informations de l'utilisateur connecté."""
        if not st.session_state.get('authentication_status'):
            return {}
        
        return {
            'username': st.session_state.get('username'),
            'name': st.session_state.get('name'),
            'role': st.session_state.get('role'),
            'permissions': st.session_state.get('permissions', []),
            'authenticated': True
        }


# Fonction helper pour obtenir l'instance
def get_auth_manager() -> AuthManager:
    """Retourne l'instance du gestionnaire d'authentification."""
    if 'auth_manager' not in st.session_state:
        st.session_state['auth_manager'] = AuthManager()
    return st.session_state['auth_manager']


# Export
__all__ = ['AuthManager', 'get_auth_manager']
