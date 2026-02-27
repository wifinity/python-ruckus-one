"""APs (Access Points) resource."""

import logging
from typing import Any, Dict, List, Optional, Union, cast

from ruckus_one.exceptions import RuckusOneAPIError, RuckusOneNotFoundError

logger = logging.getLogger(__name__)


class APsResource:
    """Resource for managing access points."""

    def __init__(self, client: Any) -> None:
        """Initialize APs resource.

        Args:
            client: RuckusOneClient instance
        """
        self.client = client
        logger.debug("Initialized APsResource")

    def _get_path(self) -> str:
        """Get base path for AP operations.

        Returns:
            Base path for AP operations (/venues/aps per Postman)
        """
        return "/venues/aps"

    def get_by_serial(
        self, venue_id: Union[int, str], serial_number: str
    ) -> Dict[str, Any]:
        """Get AP by serial number using direct lookup.

        This uses the /venues/aps/{serialNumber} endpoint exposed by the API.

        Args:
            venue_id: Venue ID (retained for backwards compatibility; not used)
            serial_number: AP serial number

        Returns:
            AP data

        Raises:
            RuckusOneNotFoundError: If AP not found
        """
        path = f"{self._get_path()}/{serial_number}"
        response = self.client.get(path)
        if not response:
            raise RuckusOneNotFoundError(f"AP with serial {serial_number} not found")
        return cast(Dict[str, Any], response)

    def list(
        self, venue_id: Optional[Union[int, str]] = None, **filters: Any
    ) -> List[Dict[str, Any]]:
        """List APs, optionally filtered by venue.

        Args:
            venue_id: Optional venue ID for filtering
            **filters: Optional filter parameters (e.g., serialNumber)

        Returns:
            List of APs
        """
        path = self._get_path()
        params = filters.copy() if filters else {}
        if venue_id:
            params["venueId"] = str(venue_id)
        response = self.client.get(path, params=params if params else None)
        if not response:
            return []

        # Handle both dict-with-data and bare list responses
        if isinstance(response, list):
            return cast(List[Dict[str, Any]], response)

        data = response.get("data", [])
        return cast(List[Dict[str, Any]], data)

    def create(self, venue_id: Union[int, str], **kwargs: Any) -> Dict[str, Any]:
        """Create/add an AP to a venue.

        Per Postman collection, POST /venues/aps expects an array of AP objects.

        Args:
            venue_id: Venue ID (will be added to AP data)
            **kwargs: AP data to create (name, serialNumber, description, tags, etc.)

        Returns:
            Created AP data (may include requestId for async operations)

        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields before creating the data dict
        required_fields = ["serialNumber", "name"]
        missing = []
        for field in required_fields:
            value = kwargs.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field)

        if missing:
            raise ValueError(
                f"Missing required fields for create: {', '.join(missing)}"
            )

        # Ensure venueId is in the data
        ap_data = kwargs.copy()
        ap_data["venueId"] = str(venue_id)

        # POST /venues/aps expects array per Postman
        path = self._get_path()
        response = self.client.post(path, json=[ap_data])
        if not response:
            raise ValueError("Failed to create AP")
        return cast(Dict[str, Any], response)

    def update(
        self,
        venue_id: Union[int, str],
        serial_number: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing AP.

        Note: Update endpoint may vary. This attempts PUT /venues/aps/{serialNumber}.

        Args:
            venue_id: Venue ID (for reference)
            serial_number: AP serial number
            data: Data to update

        Returns:
            Updated AP data (may include requestId for async operations)
        """
        # Try PUT to /venues/aps/{serialNumber}
        path = f"{self._get_path()}/{serial_number}"
        try:
            response = self.client.put(path, json=data)
            if response:
                return cast(Dict[str, Any], response)
        except RuckusOneNotFoundError:
            # Fall back to PATCH if PUT doesn't work
            logger.debug(f"PUT not available, trying PATCH for AP {serial_number}")
            # Note: httpx doesn't have PATCH directly, but we can use request method
            # For now, just raise the error
            pass

        raise ValueError(f"Failed to update AP with serial {serial_number}")

    def delete(
        self, venue_id: Union[int, str], serial_number: Union[str, List[str]]
    ) -> Optional[Dict[str, Any]]:
        """Delete one or more APs.

        Per Postman collection, DELETE /venues/aps expects JSON array of serial numbers.

        Args:
            venue_id: Venue ID (for reference, not used in API call)
            serial_number: Single serial number or list of serial numbers

        Returns:
            Response data (may include requestId for async operations)
        """
        # Normalize to list
        if isinstance(serial_number, str):
            serial_numbers = [serial_number]
        elif isinstance(serial_number, list):
            serial_numbers = serial_number
        else:
            raise ValueError(
                f"serial_number must be str or list of str, got {type(serial_number).__name__}"
            )

        # DELETE /venues/aps with JSON array body per Postman
        path = self._get_path()
        return cast(
            Optional[Dict[str, Any]], self.client.delete(path, json=serial_numbers)
        )

    def move(
        self,
        venue_id: Union[int, str],
        serial_number: str,
        target_venue_id: Union[int, str],
    ) -> Dict[str, Any]:
        """Move an AP to a different venue.

        Note: Postman collection doesn't show a direct move endpoint.
        This implementation uses delete + create as fallback.

        Args:
            venue_id: Source venue ID
            serial_number: AP serial number
            target_venue_id: Target venue ID

        Returns:
            Result of move operation
        """
        # Get AP data first
        ap_data = self.get_by_serial(venue_id, serial_number)
        # Delete from source
        self.delete(venue_id, serial_number)
        # Create in target venue (remove id and venue-specific fields, keep essential AP fields)
        create_data = {
            k: v
            for k, v in ap_data.items()
            if k not in ("id", "venueId")
            and k in ("name", "serialNumber", "description", "tags")
        }
        return self.create(target_venue_id, **create_data)

    def collect_neighbors(
        self,
        venue_id: Union[int, str],
        serial_number: str,
        neighbor_type: str = "LLDP_NEIGHBOR",
    ) -> Dict[str, Any]:
        """Trigger neighbor collection/scan for an AP.

        The AP does not always have a live, constant list of neighbors.
        The data must be collected (scanned) before it can be queried.

        Args:
            venue_id: Venue ID
            serial_number: AP serial number
            neighbor_type: Type of neighbors to collect, "LLDP_NEIGHBOR" or "RF_NEIGHBOR" (default: "LLDP_NEIGHBOR")

        Returns:
            Response data (typically includes requestId, may return 202 Accepted)
            The AP will perform the scan asynchronously

        Raises:
            RuckusOneAPIError: If the request fails
        """
        path = f"/venues/{venue_id}/aps/{serial_number}/neighbors"
        payload = {
            "status": "CURRENT",
            "type": neighbor_type,
        }
        response = self.client.patch(path, json=payload)
        if not response:
            raise ValueError(
                f"Failed to trigger neighbor collection for AP {serial_number} in venue {venue_id}"
            )
        return cast(Dict[str, Any], response)

    def _handle_lldp_neighbor_error(
        self,
        e: RuckusOneAPIError,
        venue_id: Union[int, str],
        serial_number: str,
    ) -> List[Dict[str, Any]]:
        """Handle LLDP neighbor query errors.

        Args:
            e: The caught RuckusOneAPIError
            venue_id: Venue ID
            serial_number: AP serial number

        Returns:
            Empty list if WIFI-10498 error, otherwise re-raises
        """
        if e.status_code == 400:
            error_data = e.response_data or {}
            errors = error_data.get("errors", [])
            for error in errors:
                if error.get("code") == "WIFI-10498":
                    logger.debug(
                        f"No LLDP neighbor data available for AP {serial_number} in venue {venue_id}"
                    )
                    return []
        raise

    def get_lldp_neighbors(
        self,
        venue_id: Union[int, str],
        serial_number: str,
        page: int = 1,
        page_size: int = 25,
        sort_field: Optional[str] = None,
        sort_order: str = "ASC",
    ) -> List[Dict[str, Any]]:
        """Get LLDP neighbors for an AP.

        Args:
            venue_id: Venue ID
            serial_number: AP serial number
            page: Page number (default: 1)
            page_size: Page size (default: 25)
            sort_field: Optional field to sort by
            sort_order: Sort order, "ASC" or "DESC" (default: "ASC")

        Returns:
            List of LLDP neighbor data (neighbor device name, interface, chassis ID)
            Returns empty list if no neighbor data is available

        Raises:
            RuckusOneNotFoundError: If AP not found
        """
        path = f"/venues/{venue_id}/aps/{serial_number}/neighbors/query"
        payload = {
            "filters": [{"type": "LLDP_NEIGHBOR"}],
            "page": page,
            "pageSize": page_size,
        }
        if sort_field:
            payload["sortField"] = sort_field
        if sort_order:
            payload["sortOrder"] = sort_order

        try:
            response = self.client.post(path, json=payload)
            if not response:
                return []
            # Handle response structure per docs: response has "neighbors" field
            if isinstance(response, list):
                return cast(List[Dict[str, Any]], response)
            # Check for "neighbors" field first (per API docs)
            if "neighbors" in response:
                return cast(List[Dict[str, Any]], response.get("neighbors", []))
            # Fallback to "data" field
            data = response.get("data", [])
            return cast(List[Dict[str, Any]], data)
        except RuckusOneAPIError as e:
            # Handle "No detected neighbor data" error gracefully
            return self._handle_lldp_neighbor_error(e, venue_id, serial_number)
