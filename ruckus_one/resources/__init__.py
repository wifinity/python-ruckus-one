"""Resource classes for Ruckus One API."""

from ruckus_one.resources.activities import ActivitiesResource
from ruckus_one.resources.ap_groups import APGroupsResource
from ruckus_one.resources.aps import APsResource
from ruckus_one.resources.base import BaseResource
from ruckus_one.resources.venues import VenuesResource
from ruckus_one.resources.wifi_networks import WiFiNetworksResource

__all__ = [
    "BaseResource",
    "VenuesResource",
    "APsResource",
    "WiFiNetworksResource",
    "APGroupsResource",
    "ActivitiesResource",
]
