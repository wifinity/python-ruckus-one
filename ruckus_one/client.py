"""Main client for Ruckus One API."""

import json
import logging
import re
import time
from json import JSONDecodeError
from typing import Any, Dict, List, Optional, Type, Union, cast

import httpx

from ruckus_one.auth import OAuth2TokenManager
from ruckus_one.exceptions import (
    RuckusOneAPIError,
    RuckusOneAuthenticationError,
    RuckusOneConnectionError,
    RuckusOneNotFoundError,
    RuckusOnePermissionError,
    RuckusOneValidationError,
)
from ruckus_one.logging_config import (
    format_request_body,
    format_response_body,
    mask_sensitive_headers,
    set_log_level,
)
from ruckus_one.resources import (
    APGroupsResource,
    APsResource,
    ActivitiesResource,
    VenuesResource,
    WiFiNetworksResource,
)

logger = logging.getLogger(__name__)


class RuckusOneClient:
    """Client for interacting with Ruckus One API."""

    def __init__(
        self,
        region: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        delegated_tenant_id: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        enable_retry: bool = True,
        log_level: Union[str, int, None] = None,
    ) -> None:
        """Initialize the Ruckus One client.

        Args:
            region: API region ("us", "eu", or "asia")
            tenant_id: Tenant ID for API requests
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            delegated_tenant_id: Optional delegated tenant ID (sets x-rks-tenantid header)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            enable_retry: Whether to enable automatic retries
            log_level: Log level for the client (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                       or None to use default/global setting
        """
        self.region = region
        self.tenant_id = tenant_id
        self.delegated_tenant_id = delegated_tenant_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.enable_retry = enable_retry
        self.log_level = log_level

        # Initialize OAuth2 token manager
        self.auth = OAuth2TokenManager(
            region=region,
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

        # Configure logging if log_level is provided
        if log_level is not None:
            set_log_level(log_level)

        # Get base URL from auth manager
        self.base_url = self.auth.base_url

        # Initialize HTTP client
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
        )

        # Initialize resources
        self.venues = VenuesResource(self)
        self.aps = APsResource(self)
        self.wifi_networks = WiFiNetworksResource(self)
        self.ap_groups = APGroupsResource(self)
        self.activities = ActivitiesResource(self)

        logger.debug(
            f"RuckusOneClient initialized with region={region}, "
            f"tenant_id={tenant_id}, base_url={self.base_url}"
        )

    def __enter__(self) -> "RuckusOneClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
        logger.debug("HTTP client closed")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests, including authentication.

        Returns:
            Dictionary of headers
        """
        headers = self.auth.get_headers()

        # Add delegated tenant ID header if specified
        if self.delegated_tenant_id:
            headers["x-rks-tenantid"] = self.delegated_tenant_id

        return headers

    def _extract_single_error_message(self, error: Dict[str, Any]) -> Optional[str]:
        """Extract error message from a single error dict.

        Args:
            error: Error dictionary with message, reason, and/or value

        Returns:
            Extracted error message string, or None if no valid message found
        """
        message = error.get("message")
        reason = error.get("reason")
        value = error.get("value")

        if message and reason:
            return f"{cast(str, message)} - {cast(str, reason)}"
        elif message:
            return cast(str, message)
        elif value:
            return cast(str, value)
        elif reason:
            return cast(str, reason)
        return None

    def _extract_messages_from_errors(self, errors: List[Dict[str, Any]]) -> List[str]:
        """Extract error messages from a list of error dictionaries.

        Args:
            errors: List of error dictionaries

        Returns:
            List of extracted error messages
        """
        error_messages = []
        for error in errors:
            if isinstance(error, dict):
                msg = self._extract_single_error_message(error)
                if msg and str(msg).lower() != "null" and msg:
                    error_messages.append(str(msg))
        return error_messages

    def _extract_error_messages(  # noqa: C901
        self, response_data: Optional[Dict[str, Any]], response: httpx.Response
    ) -> List[str]:
        """Extract helpful error messages from ErrorResponse structure.

        Args:
            response_data: Parsed response data (dict or None)
            response: HTTP response object

        Returns:
            List of error messages extracted from the response
        """
        error_messages = []

        if isinstance(response_data, dict):
            # Check for ErrorResponse.errors array
            errors = response_data.get("errors", [])
            error_messages.extend(self._extract_messages_from_errors(errors))

            # Also check top-level message
            top_level_msg = response_data.get("message")
            if top_level_msg and str(top_level_msg).lower() != "null":
                if top_level_msg not in error_messages:
                    error_messages.insert(0, top_level_msg)

            # If we have text but no parsed errors, try to extract from text
            # (handles cases where response is text/plain but contains error info)
            if not error_messages and "text" in response_data:
                text = response_data["text"]
                # Try to parse as JSON one more time from text
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        errors = parsed.get("errors", [])
                        error_messages.extend(
                            self._extract_messages_from_errors(errors)
                        )
                except Exception:
                    # If JSON parsing fails, try regex to extract error messages
                    # Look for patterns like "message=Country should not be empty."
                    matches = re.findall(r"message=([^,)]+)", text)
                    for match in matches:
                        if match and match.lower() != "null":
                            error_messages.append(match.strip())

        # If still no messages, try parsing response text directly as JSON
        # (handles cases where response.json() failed but text is valid JSON)
        if not error_messages and response.text:
            try:
                parsed = json.loads(response.text)
                if isinstance(parsed, dict):
                    errors = parsed.get("errors", [])
                    error_messages.extend(self._extract_messages_from_errors(errors))
            except Exception:
                # If JSON parsing fails, try regex to extract error messages from string representation
                # Look for patterns like "message=Country should not be empty." or "value=Country should not be empty."
                # Try to extract from message= or value= patterns
                message_matches = re.findall(
                    r"message=([^,)]+?)(?:,|\))", response.text
                )
                value_matches = re.findall(r"value=([^,)]+?)(?:,|\))", response.text)
                for match in message_matches + value_matches:
                    cleaned = match.strip().rstrip(".")
                    if cleaned and cleaned.lower() != "null" and len(cleaned) > 3:
                        error_messages.append(cleaned)

        return error_messages

    def _raise_error_for_status(
        self,
        status_code: int,
        response_data: Optional[Dict[str, Any]],
        response: httpx.Response,
        default_message: str,
        exception_class: Type[RuckusOneAPIError],
        errors: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Raise appropriate exception for an error status code.

        Args:
            status_code: HTTP status code
            response_data: Parsed response data
            response: HTTP response object
            default_message: Default error message if extraction fails
            exception_class: Exception class to raise
            errors: Optional list of validation errors (for RuckusOneValidationError)

        Raises:
            exception_class: The specified exception with extracted error message
        """
        error_messages = self._extract_error_messages(response_data, response)

        if error_messages:
            error_msg = "; ".join(error_messages)
        else:
            error_msg = (
                response_data.get("message", default_message)
                if isinstance(response_data, dict)
                else default_message
            )

        # Special handling for 401 (clear token cache)
        if status_code == 401:
            self.auth.clear_token()

        # RuckusOneAPIError requires status_code parameter
        if exception_class == RuckusOneAPIError:
            raise exception_class(
                error_msg, status_code=status_code, response_data=response_data
            )
        elif exception_class == RuckusOneValidationError:
            # RuckusOneValidationError requires errors parameter
            if errors is None:
                errors = (
                    response_data.get("errors", [])
                    if isinstance(response_data, dict)
                    else []
                )
            # Type checker needs explicit cast since exception_class is Type[RuckusOneAPIError]
            validation_error = RuckusOneValidationError(
                error_msg, response_data=response_data, errors=errors
            )
            raise validation_error
        else:
            raise exception_class(error_msg, response_data=response_data)

    def _handle_response(  # noqa: C901
        self, response: httpx.Response
    ) -> Optional[Dict[str, Any]]:
        """Handle HTTP response and raise appropriate exceptions.

        Args:
            response: HTTP response object

        Returns:
            Response data as dictionary, or None if no content

        Raises:
            RuckusOneAuthenticationError: For 401 errors
            RuckusOnePermissionError: For 403 errors
            RuckusOneNotFoundError: For 404 errors
            RuckusOneValidationError: For 422 errors
            RuckusOneAPIError: For other API errors
        """
        status_code = response.status_code

        # Try to parse JSON response (even if content-type is text/plain)
        response_data = None
        if response.content:
            try:
                response_data = response.json()
            except Exception:
                # If response.json() fails, try parsing the text directly as JSON
                # (handles cases where content-type is text/plain but content is JSON)
                try:
                    if response.text:
                        response_data = json.loads(response.text)
                except Exception:
                    # If JSON parsing fails, store as text for error extraction
                    response_text = response.text if response.text else ""
                    response_data = {"text": response_text}

        # Handle error status codes
        if status_code == 401:
            self._raise_error_for_status(
                status_code,
                response_data,
                response,
                "Authentication failed",
                RuckusOneAuthenticationError,
            )

        if status_code == 403:
            self._raise_error_for_status(
                status_code,
                response_data,
                response,
                "Permission denied",
                RuckusOnePermissionError,
            )

        if status_code == 404:
            self._raise_error_for_status(
                status_code,
                response_data,
                response,
                "Resource not found",
                RuckusOneNotFoundError,
            )

        if status_code == 422:
            errors = (
                response_data.get("errors", [])
                if isinstance(response_data, dict)
                else []
            )
            self._raise_error_for_status(
                status_code,
                response_data,
                response,
                "Validation error",
                RuckusOneValidationError,
                errors=errors,
            )

        if status_code == 400:
            self._raise_error_for_status(
                status_code,
                response_data,
                response,
                f"API error: {status_code}",
                RuckusOneAPIError,
            )

        if status_code >= 400:
            default_msg = (
                response_data.get("message", f"API error: {status_code}")
                if isinstance(response_data, dict)
                else f"API error: {status_code}"
            )
            self._raise_error_for_status(
                status_code, response_data, response, default_msg, RuckusOneAPIError
            )

        # Return response data for successful requests
        return response_data

    def _log_response_body(self, response: httpx.Response) -> None:
        """Log response body for debugging.

        Args:
            response: HTTP response object
        """
        # Log response body (httpx caches response content, so this is safe)
        try:
            if response.content:
                # Read content once for logging (httpx will cache it)
                content_bytes = response.content
                if content_bytes:
                    # Try to parse as JSON first
                    try:
                        response_data = json.loads(content_bytes.decode("utf-8"))
                        logger.debug(
                            f"Response body: {format_response_body(response_data)}"
                        )
                    except (ValueError, JSONDecodeError, UnicodeDecodeError):
                        # Not JSON, log as text (truncated)
                        response_text = content_bytes.decode("utf-8", errors="replace")[
                            :1000
                        ]
                        if len(content_bytes) > 1000:
                            response_text += (
                                f"... (truncated, {len(content_bytes)} bytes total)"
                            )
                        logger.debug(f"Response body: {response_text}")
                else:
                    logger.debug("Response body: <empty>")
            else:
                logger.debug("Response body: <empty>")
        except Exception as e:
            # Fallback if anything goes wrong (don't break the request)
            logger.debug(f"Response body: <error reading response: {e}>")

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Any = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: API path (absolute, starting with '/') matching Postman collection
            params: Query parameters
            json: JSON body data
            data: Form data
            files: Files to upload

        Returns:
            Response data as dictionary, or None if no content

        Raises:
            RuckusOneConnectionError: For connection errors
            RuckusOneAPIError: For API errors
        """
        # Normalize path: treat resource paths as absolute Postman-style paths.
        # Only use path as-is when it's a full URL (starting with http).
        if path.startswith("http"):
            url = path
        else:
            if not path.startswith("/"):
                path = f"/{path}"
            url = f"{self.base_url}{path}"

        # Log request details
        logger.debug(f"{method} {url}")

        # Build request body for logging
        request_body = json if json is not None else data
        if request_body:
            logger.debug(f"Request body: {format_request_body(request_body)}")

        # Get headers (includes auth and delegated tenant if set)
        headers = self._get_headers()

        # Log request headers (with sensitive data masked)
        if params:
            logger.debug(f"Query parameters: {params}")
        logger.debug(f"Request headers: {mask_sensitive_headers(headers)}")

        try:
            response = self._client.request(
                method=method,
                url=url,
                params=params,
                json=json,
                data=data,
                files=files,
                headers=headers,
            )

            # Log response details
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(
                f"Response headers: {mask_sensitive_headers(response.headers)}"
            )

            # Log response body
            self._log_response_body(response)

            return self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise RuckusOneConnectionError(
                f"Connection error: {e}", original_error=e
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            # This should be handled by _handle_response, but just in case
            raise RuckusOneAPIError(
                f"HTTP error: {e}", status_code=e.response.status_code
            ) from e

    def _request_with_retry(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Any = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method
            path: API path
            params: Query parameters
            json: JSON body data
            data: Form data
            files: Files to upload

        Returns:
            Response data
        """
        if not self.enable_retry:
            return self._request(
                method, path, params=params, json=json, data=data, files=files
            )

        # Apply retry logic manually
        delay = 1.0
        max_delay = 60.0
        exponential_base = 2.0
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                return self._request(
                    method, path, params=params, json=json, data=data, files=files
                )
            except RuckusOneConnectionError as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
                else:
                    logger.error(
                        f"All {self.max_retries + 1} attempts failed. Giving up."
                    )
            except Exception:
                # Non-retryable exception, re-raise immediately
                raise

        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in retry logic")

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a GET request.

        Args:
            path: API path
            params: Query parameters

        Returns:
            Response data
        """
        return self._request_with_retry("GET", path, params=params)

    def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        data: Any = None,
        files: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a POST request.

        Args:
            path: API path
            json: JSON body data
            data: Form data
            files: Files to upload
            params: Query parameters

        Returns:
            Response data
        """
        return self._request_with_retry(
            "POST", path, json=json, data=data, files=files, params=params
        )

    def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a PUT request.

        Args:
            path: API path
            json: JSON body data
            data: Form data
            params: Query parameters

        Returns:
            Response data
        """
        return self._request_with_retry(
            "PUT", path, json=json, data=data, params=params
        )

    def patch(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a PATCH request.

        Args:
            path: API path
            params: Query parameters
            json: JSON body data
            data: Form data

        Returns:
            Response data
        """
        return self._request_with_retry(
            "PATCH", path, json=json, data=data, params=params
        )

    def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a DELETE request.

        Args:
            path: API path
            params: Query parameters
            json: JSON body data

        Returns:
            Response data
        """
        return self._request_with_retry("DELETE", path, params=params, json=json)
