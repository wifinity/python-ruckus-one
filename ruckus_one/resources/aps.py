"""APs (Access Points) resource."""

import logging
from typing import Any, Dict, List, Optional, Union, cast

from ruckus_one.exceptions import RuckusOneAPIError, RuckusOneNotFoundError
from ruckus_one.resources.base import as_filter_values, query_all

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

    _QUERY_PATH = "/venues/aps/query"
    _LOOKUP_FIELDS = ["serialNumber", "name", "venueId", "apGroupId", "model"]

    def _get_path(self) -> str:
        """Get the path of the AP update endpoint, ``/venues/aps``."""
        return "/venues/aps"

    def _venue_ap_path(self, venue_id: Union[int, str], serial_number: str) -> str:
        return f"/venues/{venue_id}/aps/{serial_number}"

    def _find(self, serial_numbers: List[str]) -> Dict[str, Dict[str, Any]]:
        """Query rows for the given serials, keyed by serial number.

        Uses POST /venues/aps/query, which searches every venue in the tenant.
        """
        rows = query_all(
            self.client,
            self._QUERY_PATH,
            {
                "fields": self._LOOKUP_FIELDS,
                "filters": {"serialNumber": list(serial_numbers)},
            },
        )
        wanted = set(serial_numbers)
        return {
            row["serialNumber"]: row
            for row in rows
            if row.get("serialNumber") in wanted
        }

    def get_by_serial(
        self, venue_id: Union[int, str], serial_number: str
    ) -> Dict[str, Any]:
        """Get AP by serial number, in whichever venue it is registered.

        Finds the AP's venue with POST /venues/aps/query, then reads its
        configuration with GET /venues/{venueId}/aps/{serialNumber}. The result
        merges both: the query row (``serialNumber``, ``name``, ``venueId``,
        ``apGroupId``, ``model``) overlaid with the configuration (``name``,
        ``description``, ``tags``, ``model``, ``deviceGps``). ``venueId`` is the
        venue the AP is in, which can differ from ``venue_id``.

        Args:
            venue_id: Venue ID used when the query row carries no ``venueId``
            serial_number: AP serial number

        Returns:
            AP data

        Raises:
            RuckusOneNotFoundError: If AP not found
        """
        row = self._find([serial_number]).get(serial_number)
        if row is None:
            raise RuckusOneNotFoundError(f"AP with serial {serial_number} not found")

        ap_venue_id = str(row.get("venueId") or venue_id)
        detail = self.client.get(self._venue_ap_path(ap_venue_id, serial_number))
        if not detail:
            raise RuckusOneNotFoundError(f"AP with serial {serial_number} not found")

        return {
            **row,
            **cast(Dict[str, Any], detail),
            "serialNumber": serial_number,
            "venueId": ap_venue_id,
        }

    def list(
        self, venue_id: Optional[Union[int, str]] = None, **filters: Any
    ) -> List[Dict[str, Any]]:
        """List APs, optionally filtered by venue.

        Pages through POST /venues/aps/query. Each keyword filter becomes a
        ``filters`` entry (a scalar is wrapped in a list), e.g.
        ``serialNumber="123"`` → ``{"serialNumber": ["123"]}``.

        Args:
            venue_id: Optional venue ID for filtering
            **filters: Optional filter fields (e.g., serialNumber, apGroupId)

        Returns:
            List of AP query rows
        """
        query_filters = {key: as_filter_values(value) for key, value in filters.items()}
        if venue_id:
            query_filters["venueId"] = [str(venue_id)]
        body: Dict[str, Any] = {"filters": query_filters} if query_filters else {}
        return query_all(self.client, self._QUERY_PATH, body)

    def create(self, venue_id: Union[int, str], **kwargs: Any) -> Dict[str, Any]:
        """Create/add an AP to a venue.

        Uses POST /venues/{venueId}/aps with a single AP object.

        Args:
            venue_id: Venue ID
            **kwargs: AP data to create (name, serialNumber, description, tags, etc.)

        Returns:
            Create response: ``requestId`` and ``response.id``

        Raises:
            ValueError: If required fields are missing
        """
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

        ap_data = {k: v for k, v in kwargs.items() if k != "venueId"}
        response = self.client.post(f"/venues/{venue_id}/aps", json=ap_data)
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
        The API requires venueId and serialNumber in the request body.

        Args:
            venue_id: Venue ID (for reference)
            serial_number: AP serial number
            data: Data to update

        Returns:
            Updated AP data (may include requestId for async operations)
        """
        # Ensure body includes venueId and serialNumber (API requires them)
        payload = {**data, "venueId": str(venue_id), "serialNumber": serial_number}
        path = f"{self._get_path()}/{serial_number}"
        try:
            response = self.client.put(path, json=payload)
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

        Each AP is deleted with DELETE /venues/{venueId}/aps/{serialNumber} in
        the venue POST /venues/aps/query reports for it; ``venue_id`` is used
        for a serial the query does not find.

        Args:
            venue_id: Venue ID used for serials the query does not find
            serial_number: Single serial number or list of serial numbers

        Returns:
            The delete response (``requestId``) for a single serial number, or
            ``{"responses": [...]}`` with one response per serial for a list.
        """
        if isinstance(serial_number, str):
            serial_numbers = [serial_number]
        elif isinstance(serial_number, list):
            serial_numbers = serial_number
        else:
            raise ValueError(
                f"serial_number must be str or list of str, got {type(serial_number).__name__}"
            )
        if not serial_numbers:
            return {"responses": []}

        found = self._find(serial_numbers)
        responses = []
        for serial in serial_numbers:
            ap_venue_id = (found.get(serial) or {}).get("venueId") or venue_id
            responses.append(
                self.client.delete(self._venue_ap_path(ap_venue_id, serial))
            )

        if isinstance(serial_number, str):
            return cast(Optional[Dict[str, Any]], responses[0])
        return {"responses": responses}

    def move(
        self,
        venue_id: Union[int, str],
        serial_number: str,
        target_venue_id: Union[int, str],
    ) -> Dict[str, Any]:
        """Move an AP to a different venue.

        Reads the AP, deletes it from its current venue and creates it in the
        target venue with its name, serial number, description and tags.

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

    def get_network_settings(
        self, venue_id: Union[int, str], serial_number: str
    ) -> Dict[str, Any]:
        """Get network settings for an AP.

        Args:
            venue_id: Venue ID.
            serial_number: AP serial number.

        Returns:
            Network settings for the AP (ipType, ip, netmask, gateway,
            primaryDnsServer, secondaryDnsServer). Returns empty dict if no
            response.
        """
        path = f"/venues/{venue_id}/aps/{serial_number}/networkSettings"
        response = self.client.get(path)
        if not response:
            return {}
        return cast(Dict[str, Any], response)

    def update_network_settings(
        self,
        venue_id: Union[int, str],
        serial_number: str,
        settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update network settings for an AP.

        Supported body fields (API validates format):
            ipType: "DYNAMIC" | "STATIC" | null
            ip: IPv4 address string
            netmask: Subnet mask string
            gateway: IPv4 address string
            primaryDnsServer: IPv4 address string
            secondaryDnsServer: IPv4 address string

        Args:
            venue_id: Venue ID.
            serial_number: AP serial number.
            settings: Network settings payload to send as JSON.

        Returns:
            Updated network settings or API response.

        Raises:
            ValueError: If the request fails or returns no response.
        """
        path = f"/venues/{venue_id}/aps/{serial_number}/networkSettings"
        response = self.client.put(path, json=settings)
        if not response:
            raise ValueError(
                f"Failed to update network settings for AP {serial_number} in venue {venue_id}"
            )
        return cast(Dict[str, Any], response)
