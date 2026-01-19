"""Tests for client module."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from ruckus_one import RuckusOneClient
from ruckus_one.exceptions import (
    RuckusOneAPIError,
    RuckusOneAuthenticationError,
    RuckusOneConnectionError,
    RuckusOneNotFoundError,
    RuckusOneValidationError,
)


@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_initialization(mock_auth, mock_httpx_client):
    """Test RuckusOneClient initialization."""
    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth.return_value = mock_auth_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    assert client.region == "us"
    assert client.tenant_id == "test_tenant"
    assert client.base_url == "https://api.ruckus.cloud"
    assert client.venues is not None
    assert client.aps is not None
    assert client.wifi_networks is not None
    assert client.ap_groups is not None
    assert client.activities is not None


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_with_delegated_tenant(mock_auth, mock_httpx_client, mock_httpx_post):
    """Test RuckusOneClient with delegated tenant ID."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer test_token"}
    mock_auth.return_value = mock_auth_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
        delegated_tenant_id="delegated_tenant",
    )

    assert client.delegated_tenant_id == "delegated_tenant"
    headers = client._get_headers()
    assert "x-rks-tenantid" in headers
    assert headers["x-rks-tenantid"] == "delegated_tenant"


@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_context_manager(mock_auth, mock_httpx_client):
    """Test RuckusOneClient as context manager."""
    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth.return_value = mock_auth_instance

    mock_client_instance = MagicMock()
    mock_httpx_client.return_value = mock_client_instance

    with RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    ) as client:
        assert client is not None

    # Should have called close
    mock_client_instance.close.assert_called_once()


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_get_request(mock_auth, mock_httpx_client, mock_httpx_post):
    """Test GET request."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "1"}]}
    mock_response.content = b'{"data":[{"id":"1"}]}'
    mock_response.headers = {}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    result = client.get("/venues")
    assert result == {"data": [{"id": "1"}]}


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_handle_404_error(mock_auth, mock_httpx_client, mock_httpx_post):
    """Test handling of 404 errors."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"message": "Not found"}
    mock_response.content = b'{"message":"Not found"}'
    mock_response.headers = {}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneNotFoundError):
        client.get("/venues/123")


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_handle_422_error(mock_auth, mock_httpx_client, mock_httpx_post):
    """Test handling of 422 validation errors."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.json.return_value = {
        "message": "Validation error",
        "errors": [{"field": "name", "message": "Required"}],
    }
    mock_response.content = b'{"message":"Validation error","errors":[]}'
    mock_response.headers = {}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneValidationError) as exc_info:
        client.post("/venues", json={"invalid": "data"})
    assert len(exc_info.value.errors) > 0


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_handle_400_error_with_errorresponse(
    mock_auth, mock_httpx_client, mock_httpx_post
):
    """Test handling of 400 errors with ErrorResponse.errors array."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "requestId": "test-request-id",
        "errors": [
            {
                "object": "VENUE-10001.message",
                "value": "Address should not be empty.",
                "code": "VENUE-10001.message",
                "message": "Address should not be empty.",
                "reason": "Provide a valid attribute",
            }
        ],
    }
    mock_response.content = b'{"errors":[{"message":"Address should not be empty."}]}'
    mock_response.headers = {}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.post("/venues", json={"name": "Test"})

    # Should extract the helpful error message
    assert "Address should not be empty" in str(exc_info.value)
    assert exc_info.value.status_code == 400


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_handle_400_error_extract_value_field(
    mock_auth, mock_httpx_client, mock_httpx_post
):
    """Test extraction of error messages from value field when message is null."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "errors": [
            {
                "message": None,
                "value": "Address should not be empty.",
                "reason": "Provide a valid attribute",
            }
        ],
    }
    mock_response.content = b'{"errors":[{"value":"Address should not be empty."}]}'
    mock_response.headers = {}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.post("/venues", json={"name": "Test"})

    # Should extract from value field
    assert "Address should not be empty" in str(exc_info.value)


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_handle_400_error_extract_reason_field(
    mock_auth, mock_httpx_client, mock_httpx_post
):
    """Test extraction of error messages from reason field when message and value are null."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "errors": [
            {
                "message": None,
                "value": None,
                "reason": "Internal Server Error",
            }
        ],
    }
    mock_response.content = b'{"errors":[{"reason":"Internal Server Error"}]}'
    mock_response.headers = {}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.post("/venues", json={"name": "Test"})

    # Should extract from reason field
    assert "Internal Server Error" in str(exc_info.value)


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_handle_400_error_fallback(
    mock_auth, mock_httpx_client, mock_httpx_post
):
    """Test fallback when error structure is unexpected."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "message": "Bad request",
    }
    mock_response.content = b'{"message":"Bad request"}'
    mock_response.headers = {}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.post("/venues", json={"name": "Test"})

    # Should use top-level message
    assert "Bad request" in str(exc_info.value)


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_handle_400_error_multiple_errors(
    mock_auth, mock_httpx_client, mock_httpx_post
):
    """Test handling multiple error messages."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "errors": [
            {"message": "Address should not be empty."},
            {"value": "Name is required."},
        ],
    }
    mock_response.content = b'{"errors":[{"message":"Address should not be empty."}]}'
    mock_response.headers = {}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.post("/venues", json={})

    # Should combine multiple error messages
    error_msg = str(exc_info.value)
    assert "Address should not be empty" in error_msg
    assert "Name is required" in error_msg


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_handle_connection_error(mock_auth, mock_httpx_client, mock_httpx_post):
    """Test handling of connection errors."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    mock_client_instance = MagicMock()
    mock_client_instance.request.side_effect = httpx.RequestError("Connection failed")
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
        enable_retry=False,  # Disable retry to make test fast
    )

    with pytest.raises(RuckusOneConnectionError):
        client.get("/venues")


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_extract_errors_from_text_field(
    mock_auth, mock_httpx_client, mock_httpx_post
):
    """Test extracting errors from response_data['text'] field with JSON content."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    # Mock response where response.json() fails, but response_data has {"text": "..."} with JSON
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.side_effect = Exception("JSON decode error")
    mock_response.text = '{"errors": [{"message": "Error from text field"}]}'
    mock_response.content = b'{"errors": [{"message": "Error from text field"}]}'
    mock_response.headers = {"Content-Type": "text/plain"}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.get("/venues")

    # Should extract error from text field
    assert "Error from text field" in str(exc_info.value)


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_extract_errors_regex_from_text(
    mock_auth, mock_httpx_client, mock_httpx_post
):
    """Test regex extraction of error messages from text when JSON parsing fails."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    # Mock response with text containing "message=Error message" pattern
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.side_effect = Exception("JSON decode error")
    mock_response.text = (
        "Some error text with message=Country should not be empty. and other text"
    )
    mock_response.content = b"Some error text with message=Country should not be empty."
    mock_response.headers = {"Content-Type": "text/plain"}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.get("/venues")

    # Should extract error using regex
    assert "Country should not be empty" in str(exc_info.value)


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_fallback_json_parse_from_text(
    mock_auth, mock_httpx_client, mock_httpx_post
):
    """Test fallback to json.loads(response.text) when response.json() fails."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    # Mock response where response.json() raises but response.text is valid JSON
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.side_effect = Exception("JSON decode error")
    mock_response.text = '{"errors": [{"message": "Error from fallback parsing"}]}'
    mock_response.content = b'{"errors": [{"message": "Error from fallback parsing"}]}'
    mock_response.headers = {"Content-Type": "text/plain"}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.get("/venues")

    # Should extract error from fallback JSON parsing
    assert "Error from fallback parsing" in str(exc_info.value)


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_regex_extract_message_value_patterns(
    mock_auth, mock_httpx_client, mock_httpx_post
):
    """Test regex extraction of message= and value= patterns from malformed responses."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    # Mock response.text with message= and value= patterns
    # The regex looks for patterns like "message=Error, value=Value" or "message=Error)"
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.side_effect = Exception("JSON decode error")
    # Use format that matches the regex pattern: message=... or value=... with comma or closing paren
    mock_response.text = "Error: message=Name is required, value=Address is required)"
    mock_response.content = (
        b"Error: message=Name is required, value=Address is required)"
    )
    mock_response.headers = {"Content-Type": "text/plain"}

    mock_client_instance = MagicMock()
    mock_client_instance.request.return_value = mock_response
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.get("/venues")

    # Should extract message= and value= patterns using regex
    # The regex extracts patterns and filters by length > 3
    error_msg = str(exc_info.value)
    # At least one pattern should be extracted (the regex should match)
    # The exact behavior depends on how the error messages are combined
    assert "Name is required" in error_msg or "Address is required" in error_msg
    # Verify that regex extraction path was used (extracted actual content)
    assert "Name is required" in error_msg or "Address is required" in error_msg


@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_handle_http_status_error(mock_auth, mock_httpx_client, mock_httpx_post):
    """Test handling of httpx.HTTPStatusError."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    # Mock httpx.Client.request to raise HTTPStatusError
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_http_status_error = httpx.HTTPStatusError(
        "Internal Server Error", request=MagicMock(), response=mock_response
    )

    mock_client_instance = MagicMock()
    mock_client_instance.request.side_effect = mock_http_status_error
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
    )

    with pytest.raises(RuckusOneAPIError) as exc_info:
        client.get("/venues")

    # Should convert HTTPStatusError to RuckusOneAPIError
    assert exc_info.value.status_code == 500
    assert "HTTP error" in str(exc_info.value)


@patch("time.sleep")
@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_retry_multiple_attempts(
    mock_auth, mock_httpx_client, mock_httpx_post, mock_sleep
):
    """Test retry logic with multiple connection error attempts and exponential backoff."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    # Mock connection errors for first 2 attempts, success on 3rd
    success_response = MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = {"data": [{"id": "1"}]}
    success_response.content = b'{"data":[{"id":"1"}]}'
    success_response.headers = {}

    mock_client_instance = MagicMock()
    mock_client_instance.request.side_effect = [
        httpx.RequestError("Connection failed"),
        httpx.RequestError("Connection failed"),
        success_response,
    ]
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
        enable_retry=True,
        max_retries=3,
    )

    result = client.get("/venues")

    # Should succeed after retries
    assert result == {"data": [{"id": "1"}]}
    # Should have slept twice (1.0s, then 2.0s)
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list[0][0][0] == 1.0
    assert mock_sleep.call_args_list[1][0][0] == 2.0


@patch("time.sleep")
@patch("httpx.post")
@patch("httpx.Client")
@patch("ruckus_one.auth.OAuth2TokenManager")
def test_client_retry_all_attempts_fail(
    mock_auth, mock_httpx_client, mock_httpx_post, mock_sleep
):
    """Test retry logic when all attempts fail."""
    # Mock token fetch response to prevent real HTTP calls
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "test_token",
        "expires_in": 3600,
    }
    mock_token_response.text = '{"access_token":"test_token","expires_in":3600}'
    mock_token_response.headers = {"Content-Type": "application/json"}
    mock_httpx_post.return_value = mock_token_response

    mock_auth_instance = MagicMock()
    mock_auth_instance.base_url = "https://api.ruckus.cloud"
    mock_auth_instance.get_token.return_value = "test_token"
    mock_auth_instance.get_headers.return_value = {"Authorization": "Bearer token"}
    mock_auth.return_value = mock_auth_instance

    # Mock connection errors for all attempts
    mock_client_instance = MagicMock()
    mock_client_instance.request.side_effect = httpx.RequestError("Connection failed")
    mock_httpx_client.return_value = mock_client_instance

    client = RuckusOneClient(
        region="us",
        tenant_id="test_tenant",
        client_id="test_client",
        client_secret="test_secret",
        enable_retry=True,
        max_retries=2,  # 3 total attempts (0, 1, 2)
    )

    with pytest.raises(RuckusOneConnectionError):
        client.get("/venues")

    # Should have slept twice (1.0s, then 2.0s) before giving up
    assert mock_sleep.call_count == 2
