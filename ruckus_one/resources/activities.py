"""Activities resource for async operation polling."""

import logging
import time
from typing import Any, Dict, Optional, Tuple, cast

from ruckus_one.exceptions import RuckusOneAsyncOperationError, RuckusOneNotFoundError

logger = logging.getLogger(__name__)


class ActivitiesResource:
    """Resource for polling async operation status."""

    def __init__(self, client: Any) -> None:
        """Initialize activities resource.

        Args:
            client: RuckusOneClient instance
        """
        self.client = client
        logger.debug("Initialized ActivitiesResource")

    def get(self, request_id: str) -> Dict[str, Any]:
        """Get activity status by request ID.

        Per Postman collection, GET /activities/{requestId}.

        Args:
            request_id: Request ID from async operation

        Returns:
            Activity status data

        Raises:
            RuckusOneNotFoundError: If activity not found
        """
        path = f"/activities/{request_id}"
        response = self.client.get(path)
        if not response:
            raise RuckusOneNotFoundError(
                f"Activity with request_id {request_id} not found"
            )
        return cast(Dict[str, Any], response)

    def _check_timeout(self, elapsed: float, timeout: float, request_id: str) -> None:
        """Raise if elapsed time exceeds timeout."""
        if elapsed > timeout:
            raise RuckusOneAsyncOperationError(
                f"Operation timed out after {timeout} seconds",
                request_id=request_id,
            )

    def _process_activity_status(
        self, activity: Dict[str, Any], request_id: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Process activity status. Returns (done, result)."""
        status = activity.get("status", "").upper()

        if status == "SUCCESS":
            return True, activity

        if status in ("FAIL", "FAILED", "ERROR", "CANCELLED"):
            error_msg = activity.get("error") or activity.get("message")
            if not error_msg:
                error_msg = f"Operation {status.lower()}"
            elif not isinstance(error_msg, str):
                error_msg = str(error_msg)
            raise RuckusOneAsyncOperationError(
                f"Operation failed: {error_msg}",
                request_id=request_id,
                response_data=activity,
            )

        return False, None

    def wait_for_completion(
        self,
        request_id: str,
        timeout: float = 300.0,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Poll activity until completion or timeout.

        Args:
            request_id: Request ID from async operation
            timeout: Maximum time to wait in seconds (default: 300)
            poll_interval: Time between polls in seconds (default: 2.0)

        Returns:
            Final activity status data

        Raises:
            RuckusOneAsyncOperationError: If operation fails or times out
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            self._check_timeout(elapsed, timeout, request_id)

            try:
                activity = self.get(request_id)
                logger.debug(
                    f"Activity {request_id} status: {activity.get('status', '')} "
                    f"(elapsed: {elapsed:.1f}s)"
                )

                done, result = self._process_activity_status(activity, request_id)
                if done:
                    logger.info(f"Activity {request_id} completed successfully")
                    return cast(Dict[str, Any], result)

                time.sleep(poll_interval)

            except RuckusOneNotFoundError:
                # Activity not found - might be transient or already completed
                # Wait a bit and retry
                logger.debug(f"Activity {request_id} not found, retrying...")
                time.sleep(poll_interval)
                continue
            except RuckusOneAsyncOperationError:
                # Re-raise async operation errors
                raise
            except Exception as e:
                logger.error(f"Error polling activity {request_id}: {e}")
                raise RuckusOneAsyncOperationError(
                    f"Error polling activity: {e}",
                    request_id=request_id,
                ) from e
