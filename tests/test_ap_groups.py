"""Tests for AP groups resource."""

from unittest.mock import MagicMock

import pytest

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.ap_groups import APGroupsResource


def test_ap_groups_resource_initialization(mock_client):
    """Test APGroupsResource initialization."""
    resource = APGroupsResource(mock_client)
    assert resource.client == mock_client


def test_ap_groups_list(mock_client):
    """Test listing AP groups in a venue."""
    mock_client.get.return_value = {
        "data": [{"id": "1", "name": "Group 1"}],
    }

    resource = APGroupsResource(mock_client)
    groups = resource.list("venue_1")

    assert len(groups) == 1
    assert groups[0]["name"] == "Group 1"
    mock_client.get.assert_called_once_with("/venues/venue_1/apGroups")


def test_ap_groups_create(mock_client):
    """Test creating an AP group."""
    mock_client.post.return_value = {"id": "1", "name": "New Group"}

    resource = APGroupsResource(mock_client)
    group = resource.create("venue_1", name="New Group")

    assert group["name"] == "New Group"
    mock_client.post.assert_called_once_with(
        "/venues/venue_1/apGroups", json={"name": "New Group"}
    )


def test_ap_groups_create_missing_required_field(mock_client):
    """Test creating an AP group without required name field."""
    resource = APGroupsResource(mock_client)

    with pytest.raises(ValueError, match="Missing required fields for create: name"):
        resource.create("venue_1", description="Test group")


def test_ap_groups_get_by_name(mock_client):
    """Test getting AP group by name using client-side filtering."""
    mock_client.get.return_value = {
        "data": [
            {"id": "1", "name": "Test Group", "venueId": "venue_1"},
            {"id": "2", "name": "Other Group", "venueId": "venue_1"},
        ]
    }

    resource = APGroupsResource(mock_client)
    group = resource.get_by_name("venue_1", "Test Group")

    assert group["name"] == "Test Group"
    assert group["id"] == "1"
    mock_client.get.assert_called_once_with("/venues/venue_1/apGroups")


def test_ap_groups_get_by_name_not_found(mock_client):
    """Test getting AP group by name when not found."""
    mock_client.get.return_value = {
        "data": [{"id": "1", "name": "Other Group", "venueId": "venue_1"}]
    }

    resource = APGroupsResource(mock_client)

    with pytest.raises(
        RuckusOneNotFoundError, match="AP group with name 'Missing' not found"
    ):
        resource.get_by_name("venue_1", "Missing")


def test_ap_groups_get_by_name_not_found_empty_list(mock_client):
    """Test getting AP group by name when list is empty."""
    mock_client.get.return_value = {"data": []}

    resource = APGroupsResource(mock_client)

    with pytest.raises(
        RuckusOneNotFoundError, match="AP group with name 'Missing' not found"
    ):
        resource.get_by_name("venue_1", "Missing")


def test_ap_groups_get_by_name_multiple_found(mock_client):
    """Test getting AP group by name when multiple groups found."""
    mock_client.get.return_value = {
        "data": [
            {"id": "1", "name": "Test Group", "venueId": "venue_1"},
            {"id": "2", "name": "Test Group", "venueId": "venue_1"},
            {"id": "3", "name": "Other Group", "venueId": "venue_1"},
        ]
    }

    resource = APGroupsResource(mock_client)

    with pytest.raises(ValueError, match="Multiple AP groups found"):
        resource.get_by_name("venue_1", "Test Group")


def test_ap_groups_update(mock_client):
    """Test updating an AP group with keyword arguments."""
    mock_client.put.return_value = {
        "id": "1",
        "name": "Updated Group",
        "description": "1234",
    }

    resource = APGroupsResource(mock_client)
    group = resource.update("venue_1", "1", name="Updated Group", description="1234")

    assert group["description"] == "1234"
    assert group["name"] == "Updated Group"
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/apGroups/1",
        json={"name": "Updated Group", "description": "1234"},
    )


def test_ap_groups_update_multiple_fields(mock_client):
    """Test updating an AP group with multiple fields."""
    mock_client.put.return_value = {
        "id": "1",
        "name": "Updated Group",
        "description": "New description",
        "apSerialNumbers": ["ABC123", "DEF456"],
    }

    resource = APGroupsResource(mock_client)
    group = resource.update(
        "venue_1",
        "1",
        name="Updated Group",
        description="New description",
        apSerialNumbers=["ABC123", "DEF456"],
    )

    assert group["name"] == "Updated Group"
    assert group["description"] == "New description"
    assert group["apSerialNumbers"] == ["ABC123", "DEF456"]
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/apGroups/1",
        json={
            "name": "Updated Group",
            "description": "New description",
            "apSerialNumbers": ["ABC123", "DEF456"],
        },
    )


def test_ap_groups_update_invalid_field_ignored(mock_client):
    """Test that invalid fields are ignored when updating."""
    mock_client.put.return_value = {
        "id": "1",
        "name": "Test Group",
        "description": "1234",
    }

    resource = APGroupsResource(mock_client)
    group = resource.update(
        "venue_1",
        "1",
        name="Test Group",
        description="1234",
        invalidField="should be ignored",
    )

    assert group["description"] == "1234"
    # Verify invalid field is not in the payload
    call_args = mock_client.put.call_args
    payload = call_args[1]["json"]
    assert "invalidField" not in payload
    assert "description" in payload
    assert "name" in payload
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/apGroups/1", json={"name": "Test Group", "description": "1234"}
    )


def test_ap_groups_update_missing_required_name(mock_client):
    """Test that updating without 'name' field raises an error."""
    resource = APGroupsResource(mock_client)

    with pytest.raises(ValueError, match="Missing required field for update: name"):
        resource.update("venue_1", "1", description="1234")


def test_ap_groups_activate_network(mock_client):
    """Test activating a network on an AP group."""
    mock_client.put.return_value = {"requestId": "req_123"}

    resource = APGroupsResource(mock_client)
    result = resource.activate_network("venue_1", "apgroup_1", "network_1")

    assert result == {"requestId": "req_123"}
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/wifiNetworks/network_1/apGroups/apgroup_1", json={}
    )


def test_ap_groups_deactivate_network(mock_client):
    """Test deactivating a network from an AP group."""
    mock_client.delete.return_value = None

    resource = APGroupsResource(mock_client)
    result = resource.deactivate_network("venue_1", "apgroup_1", "network_1")

    assert result is None
    mock_client.delete.assert_called_once_with(
        "/venues/venue_1/wifiNetworks/network_1/apGroups/apgroup_1"
    )
