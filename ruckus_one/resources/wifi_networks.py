"""Wi-Fi Networks resource."""

import logging
from typing import Any, Dict, List, Optional, Union, cast

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.base import BaseResource, query_all

logger = logging.getLogger(__name__)


class WiFiNetworksResource(BaseResource):
    """Resource for managing Wi-Fi networks (WLANs)."""

    _required_fields_create = ["name", "type", "wlan"]

    # Valid network type IDs
    _VALID_NETWORK_TYPES = ["aaa", "dpsk", "guest", "hotspot20", "open", "psk"]

    def __init__(self, client: Any) -> None:
        """Initialize Wi-Fi networks resource."""
        path = "/wifiNetworks"
        super().__init__(client, path)

    def all(self) -> List[Dict[str, Any]]:
        """Get all Wi-Fi networks by paging through POST /wifiNetworks/query.

        Rows are the query view of each network (``id``, ``name``, ``nwSubType``,
        ``ssid``, venue and AP counts, ...), not the full network object that
        ``get(id=...)`` returns.

        Returns:
            List of all networks across all pages
        """
        return query_all(self.client, f"{self.path}/query", {})

    def get(
        self, id: Optional[Union[int, str]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Get a single Wi-Fi network by ID or by filter parameters.

        A lookup by ``name`` alone resolves the ID with a ``filters.name`` query
        (matched case-insensitively on the client), then fetches the full network
        by ID, so the result has the same shape as a lookup by ID. Any other
        filter falls back to client-side filtering over ``all()``.

        Args:
            id: Network ID (optional if using filter parameters)
            **kwargs: Filter parameters to search by (e.g., name="Network Name")

        Returns:
            Network data

        Raises:
            RuckusOneNotFoundError: If no network matches
            ValueError: If multiple networks match or parameters are invalid
        """
        if id is not None or set(kwargs) != {"name"}:
            return super().get(id, **kwargs)

        name = kwargs["name"]
        rows = query_all(
            self.client,
            f"{self.path}/query",
            {"fields": ["id", "name"], "filters": {"name": [name]}},
        )
        matches = [
            row
            for row in rows
            if isinstance(row.get("name"), str) and row["name"].lower() == name.lower()
        ]

        if not matches:
            raise RuckusOneNotFoundError(f"Wi-Fi network with name '{name}' not found")
        if len(matches) > 1:
            raise ValueError(f"Multiple Wi-Fi networks found with name '{name}'")

        network_id = matches[0].get("id")
        if not network_id:
            raise ValueError(f"Wi-Fi network query result for '{name}' has no id")

        return super().get(id=network_id)

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

        Posts ``kwargs`` as the body of POST /wifiNetworks/query (``filters``,
        ``fields``, ``searchString``, ``page``, ``pageSize``, ...) and returns
        one page of query rows.

        Args:
            **kwargs: Query body

        Returns:
            List of matching networks
        """
        response = self.client.post(f"{self.path}/query", json=kwargs)
        if not response:
            return []

        if isinstance(response, list):
            return cast(List[Dict[str, Any]], response)

        data = response.get("data", [])
        return cast(List[Dict[str, Any]], data)

    def delete(
        self, id: Union[int, str], deep: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Delete a network with DELETE /wifiNetworks/{id}.

        Args:
            id: Network ID
            deep: Accepted for signature compatibility and ignored: the endpoint
                takes no options.

        Returns:
            Response data (may include requestId for async operations)
        """
        return cast(Optional[Dict[str, Any]], self.client.delete(f"{self.path}/{id}"))

    _ACTIVATION_QUERY_PAGE_SIZE = 100

    def list_venue_networks(
        self,
        venue_id: Union[int, str],
        network_id: Optional[Union[int, str]] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List networks activated at a venue.

        Uses POST /networkActivations/query, filtered on the venue and optionally the
        network, and follows every page. The endpoint reads its filter only from
        ``filters`` (a list of match objects); top-level ``venueId``/``networkId`` keys
        are ignored and return every activation in the tenant.

        Args:
            venue_id: Venue ID
            network_id: Optional network ID to filter by specific network
            fields: Optional response-field selector. Pass ``["apGroups"]`` to have
                each activation include its ``apGroups`` membership array (present
                only when ``isAllApGroups`` is False); without it the response omits
                per-AP-group membership.

        Returns:
            List of network activations for the venue
        """
        path = "/networkActivations/query"
        match: Dict[str, Any] = {"venueId": str(venue_id)}
        if network_id is not None:
            match["networkId"] = str(network_id)
        page_size = self._ACTIVATION_QUERY_PAGE_SIZE

        activations: List[Dict[str, Any]] = []
        page = 1
        while True:
            body: Dict[str, Any] = {
                "filters": [match],
                "page": page,
                "pageSize": page_size,
            }
            if fields is not None:
                body["fields"] = list(fields)
            response = self.client.post(path, json=body)
            if not response:
                break
            if isinstance(response, list):
                activations.extend(cast(List[Dict[str, Any]], response))
                break

            items = cast(List[Dict[str, Any]], response.get("data") or [])
            activations.extend(items)
            total = response.get("totalCount")
            if len(items) < page_size:
                break
            if isinstance(total, int) and len(activations) >= total:
                break
            page += 1

        return activations

    def activate_at_venue(
        self, venue_id: Union[int, str], network_id: Union[int, str]
    ) -> Dict[str, Any]:
        """Activate Wi-Fi network at a venue.

        Uses PUT /venues/{venueId}/wifiNetworks/{wifiNetworkId} with an empty
        body, so a new activation broadcasts from all AP groups
        (``isAllApGroups`` defaults to True). The PUT is idempotent: calling it
        for a network already active at the venue does not fail.

        Args:
            venue_id: Venue ID
            network_id: Wi-Fi network ID

        Returns:
            Activation result (``requestId`` for async completion)
        """
        path = f"/venues/{venue_id}/wifiNetworks/{network_id}"
        response = self.client.put(path, json={})
        if not response:
            raise ValueError(
                f"Failed to activate network {network_id} at venue {venue_id}"
            )
        return cast(Dict[str, Any], response)

    def deactivate_at_venue(
        self, venue_id: Union[int, str], network_id: Union[int, str]
    ) -> Optional[Dict[str, Any]]:
        """Deactivate a Wi-Fi network at a venue.

        Uses DELETE /venues/{venueId}/wifiNetworks/{wifiNetworkId}.

        Args:
            venue_id: Venue ID
            network_id: Wi-Fi network ID

        Returns:
            Response data (``requestId`` for async completion)
        """
        path = f"/venues/{venue_id}/wifiNetworks/{network_id}"
        return cast(Optional[Dict[str, Any]], self.client.delete(path))

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

        The caller's ``wlan`` dict is never modified: this method shapes the
        request on a copy, so a consumer that keeps its request payload (e.g. to
        compare it against what the controller reports afterwards) is unaffected.

        Payload-shaping note — ``create`` vs ``update``: ``create`` injects the
        ``wlan.type`` discriminator because the create endpoint needs it for
        polymorphic deserialization of the WLAN sub-object. The inherited
        ``update`` (``BaseResource.update``) deliberately does **not** inject it:
        a network's ``type`` is fixed at creation, and the controller reports
        ``type`` on the network rather than inside ``wlan``. The asymmetry is
        intentional, not an oversight.

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

        # Shape the request on a copy so the caller's dict is never mutated.
        # Shallow is enough: only top-level keys (ssid, type) are added below.
        wlan = dict(wlan) if wlan else {}

        # If ssid was provided as top-level parameter, add it to wlan
        if ssid is not None:
            wlan["ssid"] = ssid

        # Validate that wlan contains ssid
        if "ssid" not in wlan or not wlan["ssid"]:
            raise ValueError(
                "wlan.ssid is required (provide either ssid parameter or wlan dict with ssid)"
            )

        # API expects type discriminator inside wlan for polymorphic deserialization
        # on create only (see the create/update note in this method's docstring).
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

    def set_ap_group_scope(
        self,
        venue_id: Union[int, str],
        network_id: Union[int, str],
        *,
        all_ap_groups: bool,
    ) -> Dict[str, Any]:
        """Set whether a venue activation targets all AP groups or specific ones.

        A venue activation defaults to ``isAllApGroups=True`` (the network broadcasts
        from every AP group in the venue). Set ``all_ap_groups=False`` to switch it
        into specific-AP-group mode, after which membership is managed per group via
        ``ap_groups.activate_network`` / ``ap_groups.deactivate_network``.

        Ordering matters: this flip must complete (poll the returned ``requestId`` via
        ``client.activities.wait_for_completion``) before adding group memberships —
        membership added while ``isAllApGroups=True`` is discarded on the flip.

        Args:
            venue_id: Venue ID
            network_id: Wi-Fi network ID
            all_ap_groups: True = broadcast from all AP groups; False = specific groups.

        Returns:
            Update response (may include ``requestId`` for async completion).
        """
        return self.update_venue_settings(
            venue_id, network_id, isAllApGroups=bool(all_ap_groups)
        )
