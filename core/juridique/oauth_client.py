# core/juridique/oauth_client.py
"""
Client OAuth2 pour l'authentification aux APIs Legifrance et Judilibre.
"""
import os
import time
import requests
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
from pathlib import Path


class OAuth2Client:
    """Gestionnaire OAuth2 pour les APIs juridiques françaises."""
    
    def __init__(self, api_name: str = "legifrance"):
        """
        Initialise le client OAuth2.
        
        Args:
            api_name: "legifrance" ou "judilibre"
        """
        self.api_name = api_name
        
        # Configuration selon l'API
        if api_name == "legifrance":
            self.client_id = os.getenv("LEGIFRANCE_CLIENT_ID")
            self.client_secret = os.getenv("LEGIFRANCE_CLIENT_SECRET")
            self.token_url = "https://oauth.piste.gouv.fr/api/oauth/token"
            self.base_url = "https://api.piste.gouv.fr/cassation/judilibre/v1"
            self.scope = "openid"
        else:  # judilibre
            self.client_id = os.getenv("JUDILIBRE_CLIENT_ID")
            self.client_secret = os.getenv("JUDILIBRE_CLIENT_SECRET")
            self.token_url = "https://oauth.piste.gouv.fr/api/oauth/token"
            self.base_url = "https://api.piste.gouv.fr/cassation/judilibre/v1"
            self.scope = "openid"
        
        # Token en mémoire
        self._access_token = None
        self._token_expires_at = None
        
        # Cache des tokens sur disque
        self.token_cache_dir = Path("data/oauth_tokens")
        self.token_cache_dir.mkdir(parents=True, exist_ok=True)
        self.token_cache_file = self.token_cache_dir / f"{api_name}_token.json"
        
        # Charger le token depuis le cache si disponible
        self._load_cached_token()
    
    def _load_cached_token(self):
        """Charge le token depuis le cache disque si valide."""
        if self.token_cache_file.exists():
            try:
                with open(self.token_cache_file, 'r') as f:
                    data = json.load(f)
                
                expires_at = datetime.fromisoformat(data['expires_at'])
                if expires_at > datetime.now():
                    self._access_token = data['access_token']
                    self._token_expires_at = expires_at
                    print(f"✅ Token {self.api_name} chargé depuis le cache")
            except Exception as e:
                print(f"⚠️ Erreur chargement token cache : {e}")
    
    def _save_token_to_cache(self, token: str, expires_in: int):
        """Sauvegarde le token dans le cache disque."""
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        data = {
            'access_token': token,
            'expires_at': expires_at.isoformat(),
            'api_name': self.api_name
        }
        
        try:
            with open(self.token_cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde token : {e}")
    
    def get_access_token(self) -> str:
        """
        Obtient un access token valide, en le renouvelant si nécessaire.
        
        Returns:
            Access token OAuth2
        """
        # Vérifier si le token actuel est encore valide
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return self._access_token
        
        # Sinon, obtenir un nouveau token
        return self._request_new_token()
    
    def _request_new_token(self) -> str:
        """
        Demande un nouveau token OAuth2.
        
        Returns:
            Nouveau access token
        """
        if not self.client_id or not self.client_secret:
            raise ValueError(
                f"Variables {self.api_name.upper()}_CLIENT_ID et "
                f"{self.api_name.upper()}_CLIENT_SECRET requises"
            )
        
        # Préparer la requête OAuth2
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': self.scope
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            # Faire la requête
            response = requests.post(
                self.token_url,
                data=data,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            # Parser la réponse
            token_data = response.json()
            
            # Extraire le token et sa durée de vie
            self._access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)  # Par défaut 1h
            
            # Calculer l'expiration (avec marge de sécurité de 60 secondes)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
            
            # Sauvegarder dans le cache
            self._save_token_to_cache(self._access_token, expires_in - 60)
            
            print(f"✅ Nouveau token {self.api_name} obtenu (expire dans {expires_in}s)")
            
            return self._access_token
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"❌ Erreur OAuth2 {self.api_name} : {e}")
    
    def get_headers(self) -> Dict[str, str]:
        """
        Retourne les headers avec le token Bearer pour les requêtes API.
        
        Returns:
            Headers avec Authorization Bearer
        """
        token = self.get_access_token()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def make_request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None,
        retry_on_401: bool = True
    ) -> requests.Response:
        """
        Fait une requête authentifiée à l'API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: Endpoint relatif (ex: "/search")
            params: Query parameters
            data: Body data pour POST/PUT
            retry_on_401: Réessayer avec nouveau token si 401
        
        Returns:
            Response object
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.get_headers()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=15
            )
            
            # Si 401, le token a peut-être expiré
            if response.status_code == 401 and retry_on_401:
                print(f"⚠️ Token {self.api_name} expiré, renouvellement...")
                self._access_token = None  # Forcer le renouvellement
                self._token_expires_at = None
                
                # Réessayer avec nouveau token
                headers = self.get_headers()
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=15
                )
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur requête {self.api_name} : {e}")
            raise


# Singleton pour chaque API
_oauth_clients = {}

def get_oauth_client(api_name: str) -> OAuth2Client:
    """
    Retourne le client OAuth2 pour l'API spécifiée.
    
    Args:
        api_name: "legifrance" ou "judilibre"
    
    Returns:
        Instance OAuth2Client
    """
    if api_name not in _oauth_clients:
        _oauth_clients[api_name] = OAuth2Client(api_name)
    return _oauth_clients[api_name]


# Export
__all__ = ['OAuth2Client', 'get_oauth_client']
