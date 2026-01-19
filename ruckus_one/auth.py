"""OAuth2 authentication handling for Ruckus One API."""

import logging
import time
from typing import Any, Dict, Optional, Tuple, cast

import httpx

from ruckus_one.exceptions import RuckusOneAuthenticationError, RuckusOneConnectionError

logger = logging.getLogger(__name__)

# Region to base URL mapping
REGION_URLS = {
    "us": "https://api.ruckus.cloud",
    "eu": "https://api.eu.ruckus.cloud",
    "asia": "https://api.asia.ruckus.cloud",
}

# Default token expiry buffer (refresh 5 minutes before expiry)
DEFAULT_TOKEN_REFRESH_BUFFER = 300  # 5 minutes in seconds


def _safe_parse_response(response: httpx.Response) -> Tuple[Optional[Dict], str]:
    """Safely parse HTTP response, handling both JSON and non-JSON responses.

    Args:
        response: HTTP response object

    Returns:
        Tuple of (parsed_data, response_text):
        - parsed_data: Parsed JSON dict if response is JSON, None otherwise
        - response_text: Raw response text (truncated to 500 chars for display)
    """
    response_text = ""
    parsed_data = None

    if response.content:
        try:
            # Try to get text first
            response_text = response.text or ""
        except Exception:
            # If text extraction fails, try to decode bytes
            try:
                response_text = response.content.decode("utf-8", errors="replace")
            except Exception:
                response_text = "<Unable to decode response>"

        # Try to parse as JSON
        try:
            parsed_data = response.json()
        except Exception:
            # Not JSON, parsed_data stays None
            pass

    # Truncate response text for error messages (keep first 500 chars)
    display_text = response_text[:500] if len(response_text) > 500 else response_text
    if len(response_text) > 500:
        display_text += "..."

    return parsed_data, display_text


class OAuth2TokenManager:
    """Manages OAuth2 token acquisition and caching for Ruckus One API."""

    def __init__(
        self,
        region: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        token_refresh_buffer: int = DEFAULT_TOKEN_REFRESH_BUFFER,
    ) -> None:
        """Initialize OAuth2 token manager.

        Args:
            region: API region ("us", "eu", or "asia")
            tenant_id: Tenant ID for authentication
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            token_refresh_buffer: Seconds before token expiry to refresh (default: 300)
        """
        if region not in REGION_URLS:
            raise ValueError(
                f"Invalid region: {region}. Must be one of {list(REGION_URLS.keys())}"
            )

        self.region = region
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_refresh_buffer = token_refresh_buffer
        self.base_url = REGION_URLS[region]

        # Token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

        logger.debug(
            f"OAuth2TokenManager initialized for region={region}, tenant_id={tenant_id}"
        )

    def get_token(self) -> str:
        """Get a valid access token, fetching or refreshing as needed.

        Returns:
            Valid access token

        Raises:
            RuckusOneAuthenticationError: If authentication fails
            RuckusOneConnectionError: If connection fails
        """
        # Check if we have a valid cached token
        if self._access_token and not self._is_token_expired():
            logger.debug("Using cached access token")
            return self._access_token

        # Fetch new token
        logger.debug("Fetching new access token")
        return self._fetch_token()

    def _build_auth_error_message(
        self,
        status_code: int,
        parsed_data: Optional[Dict[str, Any]],
        response_text: str,
        content_type: str,
    ) -> str:
        """Build comprehensive authentication error message.

        Args:
            status_code: HTTP status code
            parsed_data: Parsed JSON response data
            response_text: Raw response text
            content_type: Response content type

        Returns:
            Formatted error message
        """
        error_msg = f"Authentication failed with status {status_code}"

        if parsed_data:
            error_description = (
                parsed_data.get("error_description")
                or parsed_data.get("error")
                or parsed_data.get("message")
            )
            if error_description:
                error_msg = f"{error_msg}. {error_description}"

        if response_text:
            error_msg = f"{error_msg}\nResponse Content-Type: {content_type}\nResponse body: {response_text}"

        return error_msg

    def _fetch_token(self) -> str:  # noqa: C901
        """Fetch a new access token from the OAuth2 endpoint.

        Returns:
            Access token

        Raises:
            RuckusOneAuthenticationError: If authentication fails
            RuckusOneConnectionError: If connection fails
        """
        url = f"{self.base_url}/oauth2/token/{self.tenant_id}"

        # OAuth2 client credentials flow uses form-urlencoded
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = httpx.post(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
                follow_redirects=True,
            )

            # Safely parse response (handles both JSON and non-JSON)
            parsed_data, response_text = _safe_parse_response(response)

            if response.status_code != 200:
                # Get content type for better error messages
                content_type = response.headers.get("Content-Type", "unknown")

                # Build comprehensive error message
                error_msg = self._build_auth_error_message(
                    response.status_code, parsed_data, response_text, content_type
                )

                # Log additional debugging info
                logger.error(f"OAuth URL: {url}")
                logger.error(f"Response status: {response.status_code}")
                logger.error(f"Response headers: {dict(response.headers)}")
                if parsed_data:
                    logger.error(f"Error response (JSON): {parsed_data}")
                if response_text:
                    logger.error(f"Response text: {response_text}")

                # Store response_data safely (use parsed_data if available, otherwise None)
                raise RuckusOneAuthenticationError(
                    error_msg,
                    response_data=parsed_data,
                )

            # For 200 status, response should be JSON
            if parsed_data is None:
                # Response is 200 but not valid JSON - likely an HTML error page
                content_type = response.headers.get("Content-Type", "unknown")

                # Check if it's HTML (common for authentication errors)
                if (
                    "text/html" in content_type.lower()
                    or response_text.strip().startswith("<!DOCTYPE")
                    or response_text.strip().startswith("<html")
                ):
                    error_msg = (
                        "Authentication failed: Server returned an HTML error page. "
                        "This usually indicates invalid authentication parameters. "
                        "Please check your tenant_id, client_id, client_secret, and region."
                    )
                else:
                    error_msg = (
                        f"Received status 200 but response is not valid JSON. "
                        f"Content-Type: {content_type}. "
                        f"Response body: {response_text}"
                    )

                logger.error(f"OAuth URL: {url}")
                logger.error(f"Response status: {response.status_code}")
                logger.error(f"Response Content-Type: {content_type}")
                logger.error(f"Response body (first 500 chars): {response_text}")
                raise RuckusOneAuthenticationError(
                    error_msg,
                    response_data=None,
                )

            token_data = parsed_data
            access_token = token_data.get("access_token")
            if not access_token:
                raise RuckusOneAuthenticationError(
                    "No access_token in response", response_data=token_data
                )

            # Cache the token
            self._access_token = access_token

            # Calculate expiry time
            # Default to 3600 seconds (1 hour) if expires_in not provided
            expires_in = token_data.get("expires_in", 3600)
            self._token_expires_at = (
                time.time() + expires_in - self.token_refresh_buffer
            )

            logger.debug(
                f"Token acquired, expires in {expires_in} seconds "
                f"(will refresh at {self._token_expires_at})"
            )

            return cast(str, access_token)

        except httpx.RequestError as e:
            logger.error(f"Connection error during token fetch: {e}")
            raise RuckusOneConnectionError(
                f"Connection error: {e}", original_error=e
            ) from e
        except RuckusOneAuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token fetch: {e}")
            raise RuckusOneAuthenticationError(
                f"Unexpected error during authentication: {e}"
            ) from e

    def _is_token_expired(self) -> bool:
        """Check if the cached token is expired or about to expire.

        Returns:
            True if token is expired or should be refreshed
        """
        if not self._access_token or not self._token_expires_at:
            return True

        # Check if token has expired (with buffer)
        return time.time() >= self._token_expires_at

    def clear_token(self) -> None:
        """Clear the cached token, forcing a fresh fetch on next request."""
        logger.debug("Clearing cached token")
        self._access_token = None
        self._token_expires_at = None

    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers with current token.

        Returns:
            Dictionary with Authorization header

        Raises:
            RuckusOneAuthenticationError: If authentication fails
        """
        token = self.get_token()
        return {"Authorization": f"Bearer {token}"}
