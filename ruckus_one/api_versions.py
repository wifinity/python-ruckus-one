"""Inventory of the Ruckus One endpoints this SDK calls, with pinned API versions.

Ruckus One versions each endpoint independently through content negotiation:
``Accept: application/vnd.ruckus.v<version>+json`` selects the response
version and the same media type as ``Content-Type`` selects the request body
version. A request without a vendor media type gets the latest version, so a
breaking change on Ruckus's side reaches unpinned callers immediately.

Each entry pins the version the SDK is written against. ``None`` means the
endpoint publishes no vendor media type for that direction, so plain
``application/json`` is sent. Every endpoint the SDK calls belongs in
``ENDPOINTS``: ``scripts/check_api_drift.py`` compares this list with the
published OpenAPI specs to report deprecated, removed and newer-versioned
endpoints.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Pattern, Tuple

VENDOR_MEDIA_TYPE = "application/vnd.ruckus.v{version}+json"


@dataclass(frozen=True)
class Endpoint:
    """One API operation and the versions pinned for it."""

    method: str
    path: str
    request_version: Optional[str] = None
    response_version: Optional[str] = None
    pattern: Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        segments = [
            "[^/]+" if re.fullmatch(r"\{[^}]+\}", part) else re.escape(part)
            for part in self.path.split("/")
        ]
        object.__setattr__(self, "pattern", re.compile("/".join(segments) + "$"))

    @property
    def template(self) -> str:
        """Path with parameter names erased, for comparing against other specs."""
        return normalise_template(self.path)

    def headers(self, has_body: bool) -> Dict[str, str]:
        """Content-negotiation headers for a request to this endpoint."""
        headers: Dict[str, str] = {}
        if self.response_version:
            headers["Accept"] = media_type(self.response_version)
        if has_body and self.request_version:
            headers["Content-Type"] = media_type(self.request_version)
        return headers


def media_type(version: str) -> str:
    """Vendor media type for an API version, e.g. ``1.1``."""
    return VENDOR_MEDIA_TYPE.format(version=version)


def normalise_template(path: str) -> str:
    """Replace every ``{param}`` segment with ``{}``."""
    return re.sub(r"\{[^}]+\}", "{}", path)


ENDPOINTS: Tuple[Endpoint, ...] = (
    Endpoint("GET", "/activities/{activityId}", None, "1"),
    # AP groups
    Endpoint("GET", "/venues/{venueId}/apGroups"),
    Endpoint("GET", "/venues/{venueId}/apGroups/{apGroupId}", None, "1"),
    Endpoint("POST", "/venues/{venueId}/apGroups", "1.1", "1.1"),
    Endpoint("PUT", "/venues/{venueId}/apGroups/{apGroupId}", "1", "1"),
    Endpoint(
        "PUT",
        "/venues/{venueId}/wifiNetworks/{wifiNetworkId}/apGroups/{apGroupId}",
        None,
        "1",
    ),
    Endpoint(
        "DELETE",
        "/venues/{venueId}/wifiNetworks/{wifiNetworkId}/apGroups/{apGroupId}",
        None,
        "1",
    ),
    # APs
    Endpoint("GET", "/venues/aps"),
    Endpoint("GET", "/venues/aps/{serialNumber}"),
    Endpoint("POST", "/venues/aps"),
    Endpoint("PUT", "/venues/aps/{serialNumber}"),
    Endpoint("DELETE", "/venues/aps"),
    Endpoint("PATCH", "/venues/{venueId}/aps/{serialNumber}/neighbors", "1", "1"),
    Endpoint("POST", "/venues/{venueId}/aps/{serialNumber}/neighbors/query", "1", "1"),
    Endpoint("GET", "/venues/{venueId}/aps/{serialNumber}/networkSettings", None, "1"),
    Endpoint("PUT", "/venues/{venueId}/aps/{serialNumber}/networkSettings", "1", "1"),
    # DPSK and RADIUS profiles
    Endpoint("POST", "/dpskServices/query", None, "2"),
    Endpoint("GET", "/dpskServices"),
    Endpoint("POST", "/radiusServerProfiles/query", "1", "1"),
    # Wi-Fi networks
    Endpoint("GET", "/networks"),
    Endpoint("GET", "/networks/{networkId}"),
    Endpoint("POST", "/networks/query"),
    Endpoint("POST", "/networks"),
    Endpoint("PUT", "/networks/{networkId}"),
    Endpoint("DELETE", "/networks/{networkId}"),
    Endpoint("POST", "/networkActivations/query", "1", None),
    Endpoint("POST", "/networkActivations"),
    Endpoint("DELETE", "/networkActivations"),
    Endpoint(
        "GET", "/venues/{venueId}/wifiNetworks/{wifiNetworkId}/settings", None, "1"
    ),
    Endpoint(
        "PUT", "/venues/{venueId}/wifiNetworks/{wifiNetworkId}/settings", "1", "1"
    ),
    # Venues
    Endpoint("GET", "/venues", None, "1"),
    Endpoint("GET", "/venues/{venueId}", None, "1"),
    Endpoint("POST", "/venues/query", "1", "1"),
    Endpoint("POST", "/venues", "1", "1"),
    Endpoint("PUT", "/venues/{venueId}", "1", "1"),
    Endpoint("DELETE", "/venues", "1", "1"),
)


def find_endpoint(method: str, path: str) -> Optional[Endpoint]:
    """Return the inventory entry matching a concrete request path, if any.

    Literal segments win over parameter segments, so ``/venues/query`` matches
    the query endpoint rather than ``/venues/{venueId}``.
    """
    method = method.upper()
    path = path.split("?", 1)[0].rstrip("/") or "/"
    matches = [
        endpoint
        for endpoint in ENDPOINTS
        if endpoint.method == method and endpoint.pattern.match(path)
    ]
    if not matches:
        return None
    return min(matches, key=lambda endpoint: endpoint.path.count("{"))
