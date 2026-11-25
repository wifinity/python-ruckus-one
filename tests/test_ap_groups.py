"""Tests for AP groups resource."""

from unittest.mock import MagicMock

import pytest

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.ap_groups import APGroupsResource


def test_ap_groups_resource_initialization(mock_client):
    """Test APGroupsResource initialization."""
    resource = APGroupsResource(mock_client)
    assert resource.client == mock_client


QUERY_BODY = {"filters": {"venueId": ["venue_1"]}, "page": 1, "pageSize": 100}


def test_ap_groups_list(mock_client):
    """list() pages through POST /venues/apGroups/query filtered on the venue."""
    mock_client.post.return_value = {
        "data": [{"id": "1", "name": "Group 1", "venueId": "venue_1"}],
        "totalCount": 1,
    }

    resource = APGroupsResource(mock_client)
    groups = resource.list("venue_1")

    assert len(groups) == 1
    assert groups[0]["name"] == "Group 1"
    mock_client.post.assert_called_once_with("/venues/apGroups/query", json=QUERY_BODY)
    mock_client.get.assert_not_called()


def test_ap_groups_list_follows_pages(mock_client):
    mock_client.post.side_effect = [
        {"data": [{"id": str(i), "venueId": "venue_1"} for i in range(100)]},
        {"data": [{"id": "100", "venueId": "venue_1"}]},
    ]

    groups = APGroupsResource(mock_client).list("venue_1")

    assert len(groups) == 101
    assert mock_client.post.call_args_list[1].kwargs["json"]["page"] == 2


def test_ap_groups_list_drops_other_venues(mock_client):
    """Rows for another venue are dropped; rows without venueId are kept."""
    mock_client.post.return_value = {
        "data": [
            {"id": "1", "venueId": "venue_1"},
            {"id": "2", "venueId": "venue_2"},
            {"id": "3"},
        ]
    }

    groups = APGroupsResource(mock_client).list("venue_1")

    assert [g["id"] for g in groups] == ["1", "3"]


def test_ap_groups_list_empty(mock_client):
    mock_client.post.return_value = None

    assert APGroupsResource(mock_client).list("venue_1") == []


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
    mock_client.post.return_value = {
        "data": [
            {"id": "1", "name": "Test Group", "venueId": "venue_1"},
            {"id": "2", "name": "Other Group", "venueId": "venue_1"},
        ]
    }

    resource = APGroupsResource(mock_client)
    group = resource.get_by_name("venue_1", "Test Group")

    assert group["name"] == "Test Group"
    assert group["id"] == "1"
    mock_client.post.assert_called_once_with("/venues/apGroups/query", json=QUERY_BODY)
    mock_client.get.assert_not_called()


def test_ap_groups_get_by_name_not_found(mock_client):
    """Test getting AP group by name when not found."""
    mock_client.post.return_value = {
        "data": [{"id": "1", "name": "Other Group", "venueId": "venue_1"}]
    }

    resource = APGroupsResource(mock_client)

    with pytest.raises(
        RuckusOneNotFoundError, match="AP group with name 'Missing' not found"
    ):
        resource.get_by_name("venue_1", "Missing")


def test_ap_groups_get_by_name_not_found_empty_list(mock_client):
    """Test getting AP group by name when list is empty."""
    mock_client.post.return_value = {"data": []}

    resource = APGroupsResource(mock_client)

    with pytest.raises(
        RuckusOneNotFoundError, match="AP group with name 'Missing' not found"
    ):
        resource.get_by_name("venue_1", "Missing")


def test_ap_groups_get_by_name_multiple_found(mock_client):
    """Test getting AP group by name when multiple groups found."""
    mock_client.post.return_value = {
        "data": [
            {"id": "1", "name": "Test Group", "venueId": "venue_1"},
            {"id": "2", "name": "Test Group", "venueId": "venue_1"},
            {"id": "3", "name": "Other Group", "venueId": "venue_1"},
        ]
    }

    resource = APGroupsResource(mock_client)

    with pytest.raises(ValueError, match="Multiple AP groups found"):
        resource.get_by_name("venue_1", "Test Group")


def test_ap_groups_get_by_name_uses_cache(mock_client):
    """A cached name reads the group by id with GET /venues/{venueId}/apGroups/{id}."""
    mock_client.post.return_value = {
        "data": [{"id": "1", "name": "Test Group", "venueId": "venue_1"}]
    }
    mock_client.get.return_value = {"id": "1", "name": "Test Group"}
    resource = APGroupsResource(mock_client)

    resource.get_by_name("venue_1", "Test Group")
    group = resource.get_by_name("venue_1", "Test Group")

    assert group["id"] == "1"
    assert mock_client.post.call_count == 1
    mock_client.get.assert_called_once_with("/venues/venue_1/apGroups/1")


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


def test_ap_groups_remove_ap_present(mock_client):
    """Removing a member serial PUTs back the group without it."""
    mock_client.get.return_value = {
        "id": "1",
        "name": "Test Group",
        "apSerialNumbers": ["ABC123", "DEF456"],
    }
    mock_client.put.return_value = {
        "id": "1",
        "name": "Test Group",
        "apSerialNumbers": ["DEF456"],
    }

    resource = APGroupsResource(mock_client)
    result = resource.remove_ap("venue_1", "1", "ABC123")

    assert result["apSerialNumbers"] == ["DEF456"]
    mock_client.get.assert_called_once_with("/venues/venue_1/apGroups/1")
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/apGroups/1",
        json={"name": "Test Group", "apSerialNumbers": ["DEF456"]},
    )


def test_ap_groups_remove_ap_absent_noop(mock_client):
    """Removing a serial that isn't a member is a no-op (no PUT)."""
    group = {
        "id": "1",
        "name": "Test Group",
        "apSerialNumbers": ["DEF456"],
    }
    mock_client.get.return_value = group

    resource = APGroupsResource(mock_client)
    result = resource.remove_ap("venue_1", "1", "ABC123")

    assert result == group
    mock_client.put.assert_not_called()


def test_ap_groups_remove_ap_empty_serials_noop(mock_client):
    """Removing from a group with no serials is a no-op (no PUT)."""
    mock_client.get.return_value = {"id": "1", "name": "Test Group"}

    resource = APGroupsResource(mock_client)
    resource.remove_ap("venue_1", "1", "ABC123")

    mock_client.put.assert_not_called()


def test_ap_groups_remove_ap_group_not_found(mock_client):
    """Removing from a missing group raises RuckusOneNotFoundError."""
    mock_client.get.return_value = None

    resource = APGroupsResource(mock_client)
    with pytest.raises(RuckusOneNotFoundError):
        resource.remove_ap("venue_1", "missing", "ABC123")

    mock_client.put.assert_not_called()
