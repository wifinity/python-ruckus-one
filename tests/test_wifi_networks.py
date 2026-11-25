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
        "/networkActivations/query",
        json={"filters": [{"venueId": "venue_1"}], "page": 1, "pageSize": 100},
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
        json={
            "filters": [{"venueId": "venue_1", "networkId": "network_1"}],
            "page": 1,
            "pageSize": 100,
        },
    )


def test_wifi_networks_list_venue_networks_with_fields(mock_client):
    """Test that the fields selector is forwarded (e.g. apGroups membership)."""
    mock_client.post.return_value = {
        "data": [
            {
                "networkId": "network_1",
                "venueId": "venue_1",
                "isAllApGroups": False,
                "apGroups": [{"apGroupId": "grp_1", "id": "membership_1"}],
            }
        ]
    }

    resource = WiFiNetworksResource(mock_client)
    activations = resource.list_venue_networks(
        "venue_1", network_id="network_1", fields=["apGroups"]
    )

    assert activations[0]["apGroups"][0]["apGroupId"] == "grp_1"
    mock_client.post.assert_called_once_with(
        "/networkActivations/query",
        json={
            "filters": [{"venueId": "venue_1", "networkId": "network_1"}],
            "page": 1,
            "pageSize": 100,
            "fields": ["apGroups"],
        },
    )


def test_wifi_networks_list_venue_networks_follows_pages(mock_client):
    """Every page of a venue's activations is fetched."""
    resource = WiFiNetworksResource(mock_client)
    resource._ACTIVATION_QUERY_PAGE_SIZE = 2
    mock_client.post.side_effect = [
        {"data": [{"id": "a1"}, {"id": "a2"}], "totalCount": 3},
        {"data": [{"id": "a3"}], "totalCount": 3},
    ]

    activations = resource.list_venue_networks("venue_1")

    assert [a["id"] for a in activations] == ["a1", "a2", "a3"]
    assert [c.kwargs["json"]["page"] for c in mock_client.post.call_args_list] == [1, 2]


def test_wifi_networks_list_venue_networks_stops_at_total_count(mock_client):
    """A full last page ends the listing once totalCount is reached."""
    resource = WiFiNetworksResource(mock_client)
    resource._ACTIVATION_QUERY_PAGE_SIZE = 2
    mock_client.post.return_value = {
        "data": [{"id": "a1"}, {"id": "a2"}],
        "totalCount": 2,
    }

    activations = resource.list_venue_networks("venue_1")

    assert len(activations) == 2
    mock_client.post.assert_called_once()


def test_wifi_networks_list_venue_networks_empty_response(mock_client):
    """An empty response is no activations."""
    mock_client.post.return_value = {}

    resource = WiFiNetworksResource(mock_client)

    assert resource.list_venue_networks("venue_1", network_id="network_1") == []


def test_wifi_networks_set_ap_group_scope_specific(mock_client):
    """Test switching a venue activation into specific-AP-group mode."""
    mock_client.put.return_value = {"requestId": "req_123"}

    resource = WiFiNetworksResource(mock_client)
    result = resource.set_ap_group_scope("venue_1", "network_1", all_ap_groups=False)

    assert result == {"requestId": "req_123"}
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/wifiNetworks/network_1/settings",
        json={"isAllApGroups": False},
    )


def test_wifi_networks_set_ap_group_scope_all(mock_client):
    """Test switching a venue activation back to all-AP-groups mode."""
    mock_client.put.return_value = {"requestId": "req_456"}

    resource = WiFiNetworksResource(mock_client)
    result = resource.set_ap_group_scope("venue_1", "network_1", all_ap_groups=True)

    assert result == {"requestId": "req_456"}
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/wifiNetworks/network_1/settings",
        json={"isAllApGroups": True},
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
        json={
            "name": "Test Network",
            "type": "psk",
            "wlan": {"ssid": "TestSSID", "type": "psk"},
        },
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
        json={
            "name": "Test Network",
            "type": "psk",
            "wlan": {"ssid": "TestSSID", "type": "psk"},
        },
    )


def test_wifi_networks_create_does_not_mutate_caller_wlan(mock_client):
    """create() must shape its request on a copy, never on the caller's wlan dict.

    A consumer that keeps its request payload (e.g. to compare it against what the
    controller reports afterwards) would be silently corrupted if the SDK folded
    ``ssid``/``type`` into the dict it was handed. Guards against re-introducing
    that mutation.
    """
    mock_client.post.return_value = {
        "id": "1",
        "name": "Test Network",
        "type": "psk",
        "wlan": {"ssid": "TestSSID"},
    }

    resource = WiFiNetworksResource(mock_client)
    caller_wlan = {"ssid": "TestSSID", "advancedCustomization": {"proxyARP": True}}
    nested = caller_wlan["advancedCustomization"]

    resource.create(name="Test Network", wlan=caller_wlan, type="psk")

    # Caller's dict is unchanged: no injected ``type`` discriminator, ssid intact,
    # and the nested dict is the same untouched object.
    assert caller_wlan == {
        "ssid": "TestSSID",
        "advancedCustomization": {"proxyARP": True},
    }
    assert "type" not in caller_wlan
    assert caller_wlan["advancedCustomization"] is nested

    # ...but the wire payload still carries the discriminator the create endpoint needs.
    sent_wlan = mock_client.post.call_args[1]["json"]["wlan"]
    assert sent_wlan["type"] == "psk"
    assert sent_wlan["ssid"] == "TestSSID"


def test_wifi_networks_create_does_not_mutate_caller_wlan_ssid_param(mock_client):
    """The ssid-as-top-level-parameter path must not populate the caller's wlan in place."""
    mock_client.post.return_value = {"id": "1", "name": "Test Network"}

    resource = WiFiNetworksResource(mock_client)
    caller_wlan = {}

    resource.create(name="Test Network", ssid="TestSSID", wlan=caller_wlan, type="open")

    # ssid was injected into the SDK's copy, not the caller's dict.
    assert caller_wlan == {}
    sent_wlan = mock_client.post.call_args[1]["json"]["wlan"]
    assert sent_wlan == {"ssid": "TestSSID", "type": "open"}


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
