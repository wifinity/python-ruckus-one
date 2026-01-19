"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import MagicMock

from ruckus_one import RuckusOneClient


@pytest.fixture
def mock_client():
    """Create a mock RuckusOneClient for testing."""
    client = MagicMock(spec=RuckusOneClient)
    client.tenant_id = "test_tenant"
    client.region = "us"
    client.base_url = "https://api.ruckus.cloud"
    return client


@pytest.fixture
def sample_token_response():
    """Sample OAuth2 token response."""
    return {
        "access_token": "test_access_token_12345",
        "token_type": "Bearer",
        "expires_in": 3600,
    }


@pytest.fixture
def sample_venue():
    """Sample venue data."""
    return {
        "id": "venue_123",
        "name": "Test Venue",
        "address": {
            "addressLine": "123 Test St",
            "city": "Test City",
            "country": "United States",
            "countryCode": "US",
        },
    }


@pytest.fixture
def sample_ap():
    """Sample AP data."""
    return {
        "id": "ap_123",
        "serialNumber": "ABC123",
        "macAddress": "00:11:22:33:44:55",
        "connectionStatus": "online",
    }


@pytest.fixture
def sample_wifi_network():
    """Sample Wi-Fi network data."""
    return {
        "id": "network_123",
        "name": "Test Network",
        "ssid": "TestSSID",
    }


@pytest.fixture
def sample_ap_group():
    """Sample AP group data."""
    return {
        "id": "apgroup_123",
        "name": "Test AP Group",
        "venueId": "venue_123",
    }
