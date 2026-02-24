"""Wi-Fi Networks resource."""

import logging
from typing import Any, Dict, List, Optional, Union, cast

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.base import BaseResource

logger = logging.getLogger(__name__)


class WiFiNetworksResource(BaseResource):
    """Resource for managing Wi-Fi networks (WLANs)."""

    _required_fields_create = ["name", "type", "wlan"]

    # Valid network type IDs
    _VALID_NETWORK_TYPES = ["aaa", "dpsk", "guest", "hotspot20", "open", "psk"]

    def __init__(self, client: Any) -> None:
        """Initialize Wi-Fi networks resource."""
        path = "/networks"
        super().__init__(client, path)

    def get_by_name(self, name: str, use_cache: bool = True) -> Dict[str, Any]:
        """Get Wi-Fi network by name, with optional caching.

        Args:
            name: Network name to search for
            use_cache: Whether to use cached name → ID mapping

        Returns:
            Network data

        Raises:
            RuckusOneNotFoundError: If network not found
            ValueError: If multiple networks found
        """
        return super().get_by_name(name, use_cache=use_cache)

    def filter(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """Get filtered list of Wi-Fi networks.

        Args:
            **kwargs: Filter parameters

        Returns:
            List of filtered networks
        """
        # Try POST /query endpoint first (Ruckus One pattern)
        query_path = f"{self.path}/query"
        try:
            response = self.client.post(query_path, json=kwargs)
        except RuckusOneNotFoundError:
            # Fall back to GET with params
            response = self.client.get(self.path, params=kwargs)

        if not response:
            return []

        # Handle both dict-with-data and bare list responses
        if isinstance(response, list):
            return cast(List[Dict[str, Any]], response)

        data = response.get("data", [])
        return cast(List[Dict[str, Any]], data)

    def delete(
        self, id: Union[int, str], deep: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Delete a network.

        Per Postman collection, DELETE /networks/{id}?deep=true.

        Args:
            id: Network ID
            deep: Whether to perform deep delete (default: True)

        Returns:
            Response data (may include requestId for async operations)
        """
        path = f"{self.path}/{id}"
        params = {"deep": "true"} if deep else {}
        return cast(Optional[Dict[str, Any]], self.client.delete(path, params=params))

    def list_venue_networks(
        self, venue_id: Union[int, str], network_id: Optional[Union[int, str]] = None
    ) -> List[Dict[str, Any]]:
        """List networks activated at a venue.

        Uses POST /networkActivations/query with body containing venueId and optionally networkId.

        Args:
            venue_id: Venue ID
            network_id: Optional network ID to filter by specific network

        Returns:
            List of network activations for the venue
        """
        path = "/networkActivations/query"
        body = {"venueId": str(venue_id)}
        if network_id is not None:
            body["networkId"] = str(network_id)
        response = self.client.post(path, json=body)
        if not response:
            return []

        # Handle both dict-with-data and bare list responses
        if isinstance(response, list):
            return cast(List[Dict[str, Any]], response)

        data = response.get("data", [])
        return cast(List[Dict[str, Any]], data)

    def activate_at_venue(
        self, venue_id: Union[int, str], network_id: Union[int, str]
    ) -> Dict[str, Any]:
        """Activate Wi-Fi network at a venue.

        Per Postman collection, POST /networkActivations with body containing
        venueId and networkId.

        Args:
            venue_id: Venue ID
            network_id: Wi-Fi network ID

        Returns:
            Activation result (may include requestId for async operations)
        """
        path = "/networkActivations"
        body = {
            "venueId": str(venue_id),
            "networkId": str(network_id),
        }
        response = self.client.post(path, json=body)
        if not response:
            raise ValueError(
                f"Failed to activate network {network_id} at venue {venue_id}"
            )
        return cast(Dict[str, Any], response)

    def deactivate_at_venue(
        self, network_venue_id: Union[int, str, List[Union[int, str]]]
    ) -> Optional[Dict[str, Any]]:
        """Deactivate network at venue.

        Per Postman collection, DELETE /networkActivations with JSON array body.

        Args:
            network_venue_id: Single network-venue association ID or list of IDs

        Returns:
            Response data (may include requestId for async operations)
        """
        # Normalize to list
        if isinstance(network_venue_id, (int, str)):
            ids = [network_venue_id]
        elif isinstance(network_venue_id, list):
            ids = network_venue_id
        else:
            raise ValueError(
                f"network_venue_id must be int, str, or list, got {type(network_venue_id).__name__}"
            )

        # Convert to strings
        ids_str = [str(id_val) for id_val in ids]

        path = "/networkActivations"
        return cast(Optional[Dict[str, Any]], self.client.delete(path, json=ids_str))

    def _validate_network_type(self, network_type: str) -> None:
        """Validate network type.

        Only accepts lowercase type IDs: aaa, dpsk, guest, hotspot20, open, psk.

        Args:
            network_type: Network type to validate

        Raises:
            ValueError: If network type is invalid
        """
        if (
            not isinstance(network_type, str)
            or network_type not in self._VALID_NETWORK_TYPES
        ):
            raise ValueError(
                f"Invalid network type '{network_type}'. "
                f"Must be one of: {', '.join(self._VALID_NETWORK_TYPES)}"
            )

    def create(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a new Wi-Fi network.

        Validates that type is one of the allowed network types and restructures
        the request body to nest ssid inside a wlan object.

        Args:
            **kwargs: Network data to create (must include name, type, and either
                     ssid as top-level param or wlan dict with ssid)

        Returns:
            Created network data (may include requestId for async operations)

        Raises:
            ValueError: If type is invalid, required fields are missing, or wlan.ssid is missing
        """
        # Validate type if provided
        if "type" in kwargs:
            self._validate_network_type(kwargs["type"])

        # Handle ssid parameter - extract it and build wlan object
        ssid = kwargs.pop("ssid", None)
        wlan = kwargs.pop("wlan", {})

        # Validate wlan is a dict if provided
        if wlan and not isinstance(wlan, dict):
            raise ValueError("wlan must be a dictionary")

        # If wlan is not provided or is empty, create it
        if not wlan:
            wlan = {}

        # If ssid was provided as top-level parameter, add it to wlan
        if ssid is not None:
            wlan["ssid"] = ssid

        # Validate that wlan contains ssid
        if "ssid" not in wlan or not wlan["ssid"]:
            raise ValueError(
                "wlan.ssid is required (provide either ssid parameter or wlan dict with ssid)"
            )

        # API expects type discriminator inside wlan for polymorphic deserialization
        network_type = kwargs.get("type")
        if network_type:
            wlan["type"] = network_type

        # Update kwargs with wlan object
        kwargs["wlan"] = wlan

        # Call super().create() with restructured data
        return super().create(**kwargs)

    def get_venue_settings(
        self, venue_id: Union[int, str], network_id: Union[int, str]
    ) -> Dict[str, Any]:
        """Get Wi-Fi network settings at a venue.

        Args:
            venue_id: Venue ID
            network_id: Wi-Fi network ID

        Returns:
            Network settings at venue

        Raises:
            RuckusOneNotFoundError: If settings not found
        """
        path = f"/venues/{venue_id}/wifiNetworks/{network_id}/settings"
        response = self.client.get(path)
        if not response:
            raise RuckusOneNotFoundError(
                f"Settings for network {network_id} not found at venue {venue_id}"
            )
        return cast(Dict[str, Any], response)

    def update_venue_settings(
        self, venue_id: Union[int, str], network_id: Union[int, str], **kwargs: Any
    ) -> Dict[str, Any]:
        """Create/update Wi-Fi network settings at a venue.

        Args:
            venue_id: Venue ID
            network_id: Wi-Fi network ID
            **kwargs: Settings data to update

        Returns:
            Updated settings (may include requestId for async operations)
        """
        path = f"/venues/{venue_id}/wifiNetworks/{network_id}/settings"
        response = self.client.put(path, json=kwargs)
        if not response:
            raise ValueError(
                f"Failed to update settings for network {network_id} at venue {venue_id}"
            )
        return cast(Dict[str, Any], response)
