"""Tests for authentication module."""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ruckus_one.auth import OAuth2TokenManager
from ruckus_one.exceptions import RuckusOneAuthenticationError, RuckusOneConnectionError


def test_token_manager_initialization():
    """Test OAuth2TokenManager initialization."""
    manager = OAuth2TokenManager(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )
    assert manager.region == "us"
    assert manager.tenant_id == "test_tenant"
    assert manager.client_id == "test_client"
    assert manager.base_url == "https://api.ruckus.cloud"


def test_token_manager_invalid_region():
    """Test OAuth2TokenManager with invalid region."""
    with pytest.raises(ValueError, match="Invalid region"):
        OAuth2TokenManager(
            region="invalid",
            tenant_id="test_tenant",
            client_id="test_client",
            client_secret="test_secret",
        )


@patch("httpx.post")
def test_fetch_token_success(mock_post):
    """Test successful token fetch."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_post.return_value = mock_response

    manager = OAuth2TokenManager(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    token = manager._fetch_token()
    assert token == "test_token"
    assert manager._access_token == "test_token"
    assert manager._token_expires_at is not None


@patch("httpx.post")
def test_fetch_token_auth_error(mock_post):
    """Test token fetch with authentication error."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": "invalid_client"}
    mock_response.text = "Unauthorized"
    mock_post.return_value = mock_response

    manager = OAuth2TokenManager(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAuthenticationError):
        manager._fetch_token()


@patch("httpx.post")
def test_fetch_token_connection_error(mock_post):
    """Test token fetch with connection error."""
    mock_post.side_effect = httpx.RequestError("Connection failed")

    manager = OAuth2TokenManager(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneConnectionError):
        manager._fetch_token()


@patch("httpx.post")
def test_get_token_caching(mock_post):
    """Test token caching."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_post.return_value = mock_response

    manager = OAuth2TokenManager(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    # First call should fetch token
    token1 = manager.get_token()
    assert token1 == "test_token"
    assert mock_post.call_count == 1

    # Second call should use cache
    token2 = manager.get_token()
    assert token2 == "test_token"
    assert mock_post.call_count == 1  # Still 1, not 2


@patch("httpx.post")
def test_get_token_refresh_on_expiry(mock_post):
    """Test token refresh when expired."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_post.return_value = mock_response

    manager = OAuth2TokenManager(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
        token_refresh_buffer=0,  # No buffer for testing
    )

    # Get token
    token1 = manager.get_token()
    assert token1 == "test_token"
    assert mock_post.call_count == 1

    # Manually expire token
    manager._token_expires_at = time.time() - 1

    # Get token again - should refresh
    token2 = manager.get_token()
    assert token2 == "test_token"
    assert mock_post.call_count == 2  # Should have fetched again


@patch.object(OAuth2TokenManager, "_is_token_expired", return_value=False)
def test_get_headers(mock_is_expired):
    """Test getting authentication headers."""
    manager = OAuth2TokenManager(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )
    manager._access_token = "test_token"

    headers = manager.get_headers()
    assert headers == {"Authorization": "Bearer test_token"}


def test_clear_token():
    """Test clearing cached token."""
    manager = OAuth2TokenManager(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )
    manager._access_token = "test_token"
    manager._token_expires_at = time.time() + 3600

    manager.clear_token()
    assert manager._access_token is None
    assert manager._token_expires_at is None
