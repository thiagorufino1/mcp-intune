import pytest
from unittest.mock import patch, MagicMock
from mcp_intune.graph.errors import AuthError


def test_get_token_returns_access_token():
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {"access_token": "fake-token-123"}

    with patch("mcp_intune.security.auth._get_app", return_value=mock_app):
        from mcp_intune.security.auth import get_token
        token = get_token()
        assert token == "fake-token-123"
        mock_app.acquire_token_for_client.assert_called_once_with(
            scopes=["https://graph.microsoft.com/.default"]
        )


def test_get_token_raises_auth_error_on_failure():
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "AADSTS70011: Invalid client secret",
    }

    with patch("mcp_intune.security.auth._get_app", return_value=mock_app):
        from mcp_intune.security.auth import get_token
        with pytest.raises(AuthError, match="Failed to acquire token"):
            get_token()
