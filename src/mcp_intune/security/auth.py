import threading
from msal import ConfidentialClientApplication
from mcp_intune.config import settings
from mcp_intune.graph.errors import AuthError

_app: ConfidentialClientApplication | None = None
_lock = threading.Lock()


def _get_app() -> ConfidentialClientApplication:
    global _app
    if _app is None:
        with _lock:
            if _app is None:
                _app = ConfidentialClientApplication(
                    client_id=settings.azure_client_id,
                    authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
                    client_credential=settings.azure_client_secret.get_secret_value(),
                )
    return _app


def get_token() -> str:
    app = _get_app()
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise AuthError(
            f"Failed to acquire token: {result.get('error_description', result.get('error', 'unknown'))}"
        )
    return result["access_token"]
