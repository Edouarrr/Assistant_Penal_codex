# core/sharepoint_config.py
"""
Configuration centralisée pour SharePoint avec mapping des variables
pour assurer la compatibilité avec les deux conventions de nommage
"""
import os
from typing import Dict, Optional

class SharePointConfig:
    """Gestion unifiée des variables SharePoint."""
    
    @staticmethod
    def get_config() -> Dict[str, str]:
        """
        Récupère la configuration SharePoint en gérant les deux conventions.
        Priorité aux nouvelles variables SHAREPOINT_*.
        """
        config = {
            'client_id': (
                os.getenv('SHAREPOINT_CLIENT_ID') or 
                os.getenv('MS_CLIENT_ID', '')
            ),
            'client_secret': (
                os.getenv('SHAREPOINT_CLIENT_SECRET') or 
                os.getenv('MS_CLIENT_SECRET', '')
            ),
            'tenant_id': (
                os.getenv('SHAREPOINT_TENANT_ID') or 
                os.getenv('MS_TENANT_ID', '')
            ),
            'site': (
                os.getenv('SHAREPOINT_SITE') or 
                os.getenv('SHAREPOINT_SITE_ID', '')
            ),
            'drive': (
                os.getenv('SHAREPOINT_DRIVE') or 
                os.getenv('SHAREPOINT_DOC_LIB', '')
            )
        }
        
        # Vérifier que toutes les variables sont présentes
        missing = [k for k, v in config.items() if not v]
        if missing:
            raise ValueError(
                f"Variables SharePoint manquantes : {', '.join(missing)}. "
                f"Utilisez SHAREPOINT_* ou MS_* (legacy)"
            )
        
        return config

    @staticmethod
    def get_graph_headers(access_token: str) -> Dict[str, str]:
        """Headers pour Microsoft Graph API."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

# Modifier src/get_sharepoint_token.py pour utiliser cette config
import os
import msal
from core.sharepoint_config import SharePointConfig

def get_token() -> str:
    """
    Récupère un token d'accès Microsoft Graph en utilisant 
    la configuration centralisée SharePoint.
    """
    config = SharePointConfig.get_config()
    
    authority = f"https://login.microsoftonline.com/{config['tenant_id']}"
    scope = ["https://graph.microsoft.com/.default"]

    app = msal.ConfidentialClientApplication(
        client_id=config['client_id'],
        client_credential=config['client_secret'],
        authority=authority
    )

    result = app.acquire_token_for_client(scopes=scope)

    if "access_token" in result:
        return result["access_token"]
    else:
        error_msg = result.get('error_description', 'Erreur inconnue')
        raise RuntimeError(f"❌ Auth MS Graph échouée : {error_msg}")
