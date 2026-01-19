"""Custom exceptions for Ruckus One API client."""

from typing import Dict, List, Optional


class RuckusOneAPIError(Exception):
    """Base exception for all Ruckus One API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error message
            status_code: HTTP status code if available
            response_data: Response data if available
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data


class RuckusOneAuthenticationError(RuckusOneAPIError):
    """Raised when authentication fails (401)."""

    def __init__(
        self,
        message: str = "Authentication failed",
        response_data: Optional[Dict] = None,
    ) -> None:
        """Initialize authentication error."""
        super().__init__(message, status_code=401, response_data=response_data)


class RuckusOnePermissionError(RuckusOneAPIError):
    """Raised when user lacks permission (403)."""

    def __init__(
        self,
        message: str = "Permission denied",
        response_data: Optional[Dict] = None,
    ) -> None:
        """Initialize permission error."""
        super().__init__(message, status_code=403, response_data=response_data)


class RuckusOneNotFoundError(RuckusOneAPIError):
    """Raised when resource is not found (404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        response_data: Optional[Dict] = None,
    ) -> None:
        """Initialize not found error."""
        super().__init__(message, status_code=404, response_data=response_data)


class RuckusOneValidationError(RuckusOneAPIError):
    """Raised when request validation fails (422)."""

    def __init__(
        self,
        message: str = "Validation error",
        response_data: Optional[Dict] = None,
        errors: Optional[List[Dict]] = None,
    ) -> None:
        """Initialize validation error.

        Args:
            message: Error message
            response_data: Response data if available
            errors: List of validation errors
        """
        super().__init__(message, status_code=422, response_data=response_data)
        self.errors = errors or []


class RuckusOneConnectionError(RuckusOneAPIError):
    """Raised when connection to API fails."""

    def __init__(
        self,
        message: str = "Connection error",
        original_error: Optional[Exception] = None,
    ) -> None:
        """Initialize connection error.

        Args:
            message: Error message
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.original_error = original_error


class RuckusOneAsyncOperationError(RuckusOneAPIError):
    """Raised when an async operation fails or times out."""

    def __init__(
        self,
        message: str = "Async operation failed",
        request_id: Optional[str] = None,
        response_data: Optional[Dict] = None,
    ) -> None:
        """Initialize async operation error.

        Args:
            message: Error message
            request_id: Request ID of the async operation
            response_data: Response data if available
        """
        super().__init__(message, response_data=response_data)
        self.request_id = request_id
