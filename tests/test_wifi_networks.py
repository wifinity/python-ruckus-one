"""Tests for Wi-Fi networks resource."""

from unittest.mock import MagicMock

import pytest

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.wifi_networks import WiFiNetworksResource


def test_wifi_networks_resource_initialization(mock_client):
    """Test WiFiNetworksResource initialization."""
    resource = WiFiNetworksResource(mock_client)
    assert resource.client == mock_client
    assert resource.path == "/networks"


def test_wifi_networks_all(mock_client):
    """Test listing all networks."""
    mock_client.get.return_value = {
        "data": [{"id": "1", "name": "Network 1"}],
        "meta": {"total": 1},
    }

    resource = WiFiNetworksResource(mock_client)
    networks = resource.all()

    assert len(networks) == 1
    assert networks[0]["name"] == "Network 1"


def test_wifi_networks_get_by_id(mock_client):
    """Test getting network by ID."""
    mock_client.get.return_value = {"id": "1", "name": "Network 1"}

    resource = WiFiNetworksResource(mock_client)
    network = resource.get(id="1")

    assert network["id"] == "1"
    assert network["name"] == "Network 1"


def test_wifi_networks_delete(mock_client):
    """Test deleting a network."""
    mock_client.delete.return_value = {"requestId": "req_123"}

    resource = WiFiNetworksResource(mock_client)
    result = resource.delete("network_1", deep=True)

    assert result == {"requestId": "req_123"}
    mock_client.delete.assert_called_once_with(
        "/networks/network_1", params={"deep": "true"}
    )


def test_wifi_networks_activate_at_venue(mock_client):
    """Test activating network at venue."""
    mock_client.post.return_value = {"requestId": "req_123"}

    resource = WiFiNetworksResource(mock_client)
    result = resource.activate_at_venue("venue_1", "network_1")

    assert result == {"requestId": "req_123"}
    mock_client.post.assert_called_once_with(
        "/networkActivations",
        json={"venueId": "venue_1", "networkId": "network_1"},
    )


def test_wifi_networks_list_venue_networks(mock_client):
    """Test listing networks at a venue."""
    mock_client.post.return_value = {
        "data": [{"networkId": "network_1", "venueId": "venue_1"}]
    }

    resource = WiFiNetworksResource(mock_client)
    activations = resource.list_venue_networks("venue_1")

    assert len(activations) == 1
    mock_client.post.assert_called_once_with(
        "/networkActivations/query", json={"venueId": "venue_1"}
    )


def test_wifi_networks_list_venue_networks_with_network_id(mock_client):
    """Test listing networks at a venue with network ID filter."""
    mock_client.post.return_value = {
        "data": [{"networkId": "network_1", "venueId": "venue_1"}]
    }

    resource = WiFiNetworksResource(mock_client)
    activations = resource.list_venue_networks("venue_1", network_id="network_1")

    assert len(activations) == 1
    mock_client.post.assert_called_once_with(
        "/networkActivations/query",
        json={"venueId": "venue_1", "networkId": "network_1"},
    )


def test_wifi_networks_deactivate_at_venue(mock_client):
    """Test deactivating network at venue."""
    mock_client.delete.return_value = {"requestId": "req_123"}

    resource = WiFiNetworksResource(mock_client)
    result = resource.deactivate_at_venue("activation_1")

    assert result == {"requestId": "req_123"}
    mock_client.delete.assert_called_once_with(
        "/networkActivations", json=["activation_1"]
    )


def test_wifi_networks_create(mock_client):
    """Test creating a Wi-Fi network with ssid as top-level parameter."""
    mock_client.post.return_value = {
        "id": "1",
        "name": "Test Network",
        "type": "psk",
        "wlan": {"ssid": "TestSSID"},
    }

    resource = WiFiNetworksResource(mock_client)
    network = resource.create(name="Test Network", ssid="TestSSID", type="psk")

    assert network["name"] == "Test Network"
    mock_client.post.assert_called_once_with(
        "/networks",
        json={"name": "Test Network", "type": "psk", "wlan": {"ssid": "TestSSID"}},
    )


def test_wifi_networks_create_with_wlan_dict(mock_client):
    """Test creating a Wi-Fi network with wlan dict provided directly."""
    mock_client.post.return_value = {
        "id": "1",
        "name": "Test Network",
        "type": "psk",
        "wlan": {"ssid": "TestSSID"},
    }

    resource = WiFiNetworksResource(mock_client)
    network = resource.create(
        name="Test Network", wlan={"ssid": "TestSSID"}, type="psk"
    )

    assert network["name"] == "Test Network"
    mock_client.post.assert_called_once_with(
        "/networks",
        json={"name": "Test Network", "type": "psk", "wlan": {"ssid": "TestSSID"}},
    )


def test_wifi_networks_create_missing_required_fields(mock_client):
    """Test creating a Wi-Fi network without required fields."""
    resource = WiFiNetworksResource(mock_client)

    # Missing all required fields - wlan.ssid check happens first
    with pytest.raises(ValueError, match="wlan.ssid is required"):
        resource.create(description="Test")

    # Missing name only
    with pytest.raises(ValueError, match="Missing required fields for create: name"):
        resource.create(wlan={"ssid": "TestSSID"}, type="psk")

    # Missing wlan only - wlan.ssid check happens before base validation
    with pytest.raises(ValueError, match="wlan.ssid is required"):
        resource.create(name="Test Network", type="psk")

    # Missing type only
    with pytest.raises(ValueError, match="Missing required fields for create: type"):
        resource.create(name="Test Network", wlan={"ssid": "TestSSID"})

    # Missing ssid in wlan
    with pytest.raises(ValueError, match="wlan.ssid is required"):
        resource.create(name="Test Network", wlan={}, type="psk")

    # Empty string for ssid in wlan
    with pytest.raises(ValueError, match="wlan.ssid is required"):
        resource.create(name="Test Network", wlan={"ssid": ""}, type="psk")

    # None value for ssid in wlan
    with pytest.raises(ValueError, match="wlan.ssid is required"):
        resource.create(name="Test Network", wlan={"ssid": None}, type="psk")

    # Empty string for type
    with pytest.raises(ValueError, match="Invalid network type"):
        resource.create(name="Test Network", wlan={"ssid": "TestSSID"}, type="")

    # None value for type
    with pytest.raises(ValueError, match="Invalid network type"):
        resource.create(name="Test Network", wlan={"ssid": "TestSSID"}, type=None)


def test_wifi_networks_create_invalid_type(mock_client):
    """Test creating a Wi-Fi network with invalid type."""
    resource = WiFiNetworksResource(mock_client)

    # Invalid type value
    with pytest.raises(
        ValueError, match="Invalid network type 'invalid'. Must be one of:"
    ):
        resource.create(name="Test Network", ssid="TestSSID", type="invalid")

    # Case sensitivity - uppercase should fail
    with pytest.raises(ValueError, match="Invalid network type 'PSK'. Must be one of:"):
        resource.create(name="Test Network", ssid="TestSSID", type="PSK")

    # Case sensitivity - mixed case should fail
    with pytest.raises(ValueError, match="Invalid network type 'Psk'. Must be one of:"):
        resource.create(name="Test Network", ssid="TestSSID", type="Psk")

    # Case sensitivity - uppercase AAA should fail
    with pytest.raises(ValueError, match="Invalid network type 'AAA'. Must be one of:"):
        resource.create(name="Test Network", ssid="TestSSID", type="AAA")


def test_wifi_networks_create_valid_types(mock_client):
    """Test creating Wi-Fi networks with all valid type values."""
    resource = WiFiNetworksResource(mock_client)
    mock_client.post.return_value = {
        "id": "1",
        "name": "Test Network",
        "type": "psk",
        "wlan": {"ssid": "TestSSID"},
    }

    # Test all valid types
    valid_types = ["aaa", "dpsk", "guest", "hotspot20", "open", "psk"]

    for network_type in valid_types:
        resource.create(name="Test Network", ssid="TestSSID", type=network_type)
        # Verify the type was included in the request and wlan structure is correct
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["type"] == network_type
        assert call_args[1]["json"]["wlan"]["ssid"] == "TestSSID"


def test_wifi_networks_get_venue_settings(mock_client):
    """Test getting Wi-Fi network settings at a venue."""
    mock_client.get.return_value = {
        "networkId": "network_1",
        "venueId": "venue_1",
        "settings": {"key": "value"},
    }

    resource = WiFiNetworksResource(mock_client)
    settings = resource.get_venue_settings("venue_1", "network_1")

    assert settings["networkId"] == "network_1"
    assert settings["venueId"] == "venue_1"
    mock_client.get.assert_called_once_with(
        "/venues/venue_1/wifiNetworks/network_1/settings"
    )


def test_wifi_networks_get_venue_settings_not_found(mock_client):
    """Test getting Wi-Fi network settings when not found."""
    mock_client.get.return_value = None

    resource = WiFiNetworksResource(mock_client)
    with pytest.raises(
        RuckusOneNotFoundError,
        match="Settings for network network_1 not found at venue venue_1",
    ):
        resource.get_venue_settings("venue_1", "network_1")


def test_wifi_networks_update_venue_settings(mock_client):
    """Test updating Wi-Fi network settings at a venue."""
    mock_client.put.return_value = {
        "networkId": "network_1",
        "venueId": "venue_1",
        "settings": {"key": "updated_value"},
    }

    resource = WiFiNetworksResource(mock_client)
    result = resource.update_venue_settings("venue_1", "network_1", key="updated_value")

    assert result["settings"]["key"] == "updated_value"
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/wifiNetworks/network_1/settings", json={"key": "updated_value"}
    )


def test_wifi_networks_update_venue_settings_multiple_fields(mock_client):
    """Test updating Wi-Fi network settings with multiple fields."""
    mock_client.put.return_value = {
        "networkId": "network_1",
        "venueId": "venue_1",
        "settings": {"key1": "value1", "key2": "value2"},
    }

    resource = WiFiNetworksResource(mock_client)
    result = resource.update_venue_settings(
        "venue_1", "network_1", key1="value1", key2="value2"
    )

    assert result["settings"]["key1"] == "value1"
    assert result["settings"]["key2"] == "value2"
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/wifiNetworks/network_1/settings",
        json={"key1": "value1", "key2": "value2"},
    )


def test_wifi_networks_update_venue_settings_failed(mock_client):
    """Test updating Wi-Fi network settings when update fails."""
    mock_client.put.return_value = None

    resource = WiFiNetworksResource(mock_client)
    with pytest.raises(
        ValueError,
        match="Failed to update settings for network network_1 at venue venue_1",
    ):
        resource.update_venue_settings("venue_1", "network_1", key="value")
