import os
import msal

def get_token() -> str:
    """
    Récupère un token d'accès Microsoft Graph en utilisant les variables
    d’environnement SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET, SHAREPOINT_TENANT_ID.

    Returns:
        str: access token à utiliser dans les appels à Microsoft Graph API.
    Raises:
        RuntimeError: si l’authentification échoue.
    """
    client_id = os.getenv("SHAREPOINT_CLIENT_ID")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
    tenant_id = os.getenv("SHAREPOINT_TENANT_ID")

    if not all([client_id, client_secret, tenant_id]):
        raise RuntimeError("❌ Variables SHAREPOINT_CLIENT_ID, CLIENT_SECRET ou TENANT_ID manquantes.")

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://graph.microsoft.com/.default"]

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority
    )

    result = app.acquire_token_for_client(scopes=scope)

    if "access_token" in result:
        return result["access_token"]
    else:
        raise RuntimeError(f"❌ Auth MS Graph échouée : {result.get('error_description')}")
