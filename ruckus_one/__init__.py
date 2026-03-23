"""Ruckus One API Python Client Library."""

__version__ = "0.1.0"

from ruckus_one.client import RuckusOneClient
from ruckus_one.exceptions import (
    RuckusOneAPIError,
    RuckusOneAsyncOperationError,
    RuckusOneAuthenticationError,
    RuckusOneConnectionError,
    RuckusOneNotFoundError,
    RuckusOnePermissionError,
    RuckusOneValidationError,
)
from ruckus_one.logging_config import set_log_level
from ruckus_one.resources import (
    APGroupsResource,
    APsResource,
    ActivitiesResource,
    BaseResource,
    DpskServicesResource,
    RadiusServerProfilesResource,
    VenuesResource,
    WiFiNetworksResource,
)

__all__ = [
    "RuckusOneClient",
    "RuckusOneAPIError",
    "RuckusOneAuthenticationError",
    "RuckusOnePermissionError",
    "RuckusOneNotFoundError",
    "RuckusOneValidationError",
    "RuckusOneConnectionError",
    "RuckusOneAsyncOperationError",
    "BaseResource",
    "VenuesResource",
    "APsResource",
    "WiFiNetworksResource",
    "APGroupsResource",
    "ActivitiesResource",
    "RadiusServerProfilesResource",
    "DpskServicesResource",
    "set_log_level",
]
