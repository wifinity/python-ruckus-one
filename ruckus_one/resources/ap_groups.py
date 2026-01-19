"""AP Groups resource."""

import logging
from typing import Any, Dict, List, Optional, Union, cast

from ruckus_one.exceptions import RuckusOneNotFoundError

logger = logging.getLogger(__name__)


class APGroupsResource:
    """Resource for managing AP groups.

    Note: AP group endpoints are not explicitly shown in the Postman collection.
    This implementation is based on assumptions and may need adjustment based on
    actual API behavior. Paths use /venues/{venueId}/apGroups pattern.
    """

    _required_fields_create = ["name"]

    def __init__(self, client: Any) -> None:
        """Initialize AP groups resource.

        Args:
            client: RuckusOneClient instance
        """
        self.client = client
        # Cache for name-based lookups per venue
        self._name_cache: Dict[str, Dict[str, str]] = {}
        logger.debug("Initialized APGroupsResource")

    def _get_path(self, venue_id: Union[int, str]) -> str:
        """Get base path for AP group operations in a venue.

        Note: This path is based on assumptions as AP groups are not explicitly
        documented in the Postman collection.

        Args:
            venue_id: Venue ID

        Returns:
            Base path for AP group operations
        """
        return f"/venues/{venue_id}/apGroups"

    def list(self, venue_id: Union[int, str]) -> List[Dict[str, Any]]:
        """List AP groups in a venue.

        Args:
            venue_id: Venue ID

        Returns:
            List of AP groups
        """
        path = self._get_path(venue_id)
        response = self.client.get(path)
        if not response:
            return []

        # Handle both dict-with-data and bare list responses
        if isinstance(response, list):
            return cast(List[Dict[str, Any]], response)

        data = response.get("data", [])
        return cast(List[Dict[str, Any]], data)

    def get(self, venue_id: Union[int, str], id: Union[int, str]) -> Dict[str, Any]:
        """Get AP group by ID.

        Args:
            venue_id: Venue ID
            id: AP group ID

        Returns:
            AP group data

        Raises:
            RuckusOneNotFoundError: If AP group not found
        """
        path = f"{self._get_path(venue_id)}/{id}"
        response = self.client.get(path)
        if not response:
            raise RuckusOneNotFoundError(
                f"AP group with id {id} not found in venue {venue_id}"
            )
        return cast(Dict[str, Any], response)

    def get_by_name(
        self,
        venue_id: Union[int, str],
        name: str,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Get AP group by name, with optional caching.

        Args:
            venue_id: Venue ID
            name: AP group name to search for
            use_cache: Whether to use cached name → ID mapping

        Returns:
            AP group data

        Raises:
            RuckusOneNotFoundError: If AP group not found
            ValueError: If multiple AP groups found
        """
        venue_key = str(venue_id)

        # Check cache first
        if use_cache and venue_key in self._name_cache:
            if name in self._name_cache[venue_key]:
                cached_id = self._name_cache[venue_key][name]
                logger.debug(
                    f"Using cached ID {cached_id} for AP group name '{name}' "
                    f"in venue {venue_id}"
                )
                return self.get(venue_id, cached_id)

        # Fetch from API using client-side filtering
        all_groups = self.list(venue_id)
        items = [g for g in all_groups if g.get("name") == name]

        if len(items) == 0:
            raise RuckusOneNotFoundError(
                f"AP group with name '{name}' not found in venue {venue_id}"
            )
        if len(items) > 1:
            raise ValueError(
                f"Multiple AP groups found ({len(items)}) with name '{name}'. "
                "Use list() to get all results or be more specific."
            )

        item = cast(Dict[str, Any], items[0])

        # Cache the name → ID mapping
        if use_cache and "id" in item:
            if venue_key not in self._name_cache:
                self._name_cache[venue_key] = {}
            self._name_cache[venue_key][name] = str(item["id"])
            logger.debug(
                f"Cached AP group name '{name}' → ID {item['id']} "
                f"for venue {venue_id}"
            )

        return item

    def create(self, venue_id: Union[int, str], **kwargs: Any) -> Dict[str, Any]:
        """Create a new AP group in a venue.

        Args:
            venue_id: Venue ID
            **kwargs: AP group data to create

        Returns:
            Created AP group data (may include requestId for async operations)

        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields
        required_fields = getattr(self, "_required_fields_create", [])
        if required_fields:
            missing = []
            for field in required_fields:
                value = kwargs.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    missing.append(field)

            if missing:
                raise ValueError(
                    f"Missing required fields for create: {', '.join(missing)}"
                )

        path = self._get_path(venue_id)
        response = self.client.post(path, json=kwargs)
        if not response:
            raise ValueError(f"Failed to create AP group in venue {venue_id}")
        return cast(Dict[str, Any], response)

    def update(
        self,
        venue_id: Union[int, str],
        id: Union[int, str],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Update an existing AP group.

        Args:
            venue_id: Venue ID
            id: AP group ID
            **kwargs: Fields to update (apSerialNumbers, description, name)
                     Note: 'name' is required

        Returns:
            Updated AP group data (may include requestId for async operations)

        Raises:
            ValueError: If 'name' field is missing
        """
        # Validate that 'name' is required
        if "name" not in kwargs:
            raise ValueError("Missing required field for update: name")

        # Build payload from kwargs, only including valid fields
        valid_fields = ["apSerialNumbers", "description", "name"]
        payload = {k: v for k, v in kwargs.items() if k in valid_fields}

        path = f"{self._get_path(venue_id)}/{id}"
        response = self.client.put(path, json=payload)
        if not response:
            raise ValueError(
                f"Failed to update AP group with id {id} in venue {venue_id}"
            )
        return cast(Dict[str, Any], response)

    def activate_network(
        self,
        venue_id: Union[int, str],
        ap_group_id: Union[int, str],
        network_id: Union[int, str],
    ) -> Dict[str, Any]:
        """Activate a Wi-Fi network on an AP group.

        Args:
            venue_id: Venue ID
            ap_group_id: AP group ID
            network_id: Wi-Fi network ID

        Returns:
            Activation result (may include requestId for async operations)
        """
        # Use correct endpoint: PUT /venues/{venueId}/wifiNetworks/{wifiNetworkId}/apGroups/{apGroupId}
        path = f"/venues/{venue_id}/wifiNetworks/{network_id}/apGroups/{ap_group_id}"
        response = self.client.put(path, json={})
        if not response:
            raise ValueError(
                f"Failed to activate network {network_id} on AP group {ap_group_id}"
            )
        return cast(Dict[str, Any], response)

    def deactivate_network(
        self,
        venue_id: Union[int, str],
        ap_group_id: Union[int, str],
        network_id: Union[int, str],
    ) -> Optional[Dict[str, Any]]:
        """Deactivate a Wi-Fi network from an AP group.

        Args:
            venue_id: Venue ID
            ap_group_id: AP group ID
            network_id: Wi-Fi network ID

        Returns:
            Deactivation result or None
        """
        # Use correct endpoint: DELETE /venues/{venueId}/wifiNetworks/{wifiNetworkId}/apGroups/{apGroupId}
        path = f"/venues/{venue_id}/wifiNetworks/{network_id}/apGroups/{ap_group_id}"
        return cast(Optional[Dict[str, Any]], self.client.delete(path))

    def clear_name_cache(self, venue_id: Optional[Union[int, str]] = None) -> None:
        """Clear the name-based lookup cache.

        Args:
            venue_id: Optional venue ID to clear cache for specific venue.
                     If None, clears cache for all venues.
        """
        if venue_id is None:
            logger.debug("Clearing name cache for all venues")
            self._name_cache.clear()
        else:
            venue_key = str(venue_id)
            if venue_key in self._name_cache:
                logger.debug(f"Clearing name cache for venue {venue_id}")
                del self._name_cache[venue_key]
