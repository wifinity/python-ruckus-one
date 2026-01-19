"""Tests for APs resource."""

from unittest.mock import MagicMock

import pytest

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.aps import APsResource


def test_aps_resource_initialization(mock_client):
    """Test APsResource initialization."""
    resource = APsResource(mock_client)
    assert resource.client == mock_client


def test_aps_get_by_serial(mock_client):
    """Test getting AP by serial number."""
    mock_client.get.return_value = {
        "serialNumber": "ABC123",
        "macAddress": "00:11:22:33:44:55",
    }

    resource = APsResource(mock_client)
    ap = resource.get_by_serial("venue_1", "ABC123")

    assert ap["serialNumber"] == "ABC123"


def test_aps_get_by_serial_not_found(mock_client):
    """Test getting AP by serial when not found."""
    mock_client.get.return_value = None

    resource = APsResource(mock_client)
    with pytest.raises(RuckusOneNotFoundError):
        resource.get_by_serial("venue_1", "INVALID")


def test_aps_list(mock_client):
    """Test listing APs in a venue."""
    mock_client.get.return_value = {
        "data": [{"serialNumber": "ABC123"}, {"serialNumber": "DEF456"}]
    }

    resource = APsResource(mock_client)
    aps = resource.list("venue_1")

    assert len(aps) == 2
    assert aps[0]["serialNumber"] == "ABC123"
    mock_client.get.assert_called_once_with(
        "/venues/aps", params={"venueId": "venue_1"}
    )


def test_aps_create(mock_client):
    """Test creating an AP."""
    mock_client.post.return_value = {"serialNumber": "ABC123", "name": "Test AP"}

    resource = APsResource(mock_client)
    ap = resource.create(
        "venue_1", serialNumber="ABC123", name="Test AP", macAddress="00:11:22:33:44:55"
    )

    assert ap["serialNumber"] == "ABC123"
    # Verify POST to /venues/aps with array body
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/venues/aps"
    assert isinstance(call_args[1]["json"], list)
    assert call_args[1]["json"][0]["venueId"] == "venue_1"
    assert call_args[1]["json"][0]["serialNumber"] == "ABC123"
    assert call_args[1]["json"][0]["name"] == "Test AP"


def test_aps_create_missing_required_field(mock_client):
    """Test creating an AP without required fields."""
    resource = APsResource(mock_client)

    # Test missing serialNumber
    with pytest.raises(
        ValueError, match="Missing required fields for create: serialNumber"
    ):
        resource.create("venue_1", name="Test AP", macAddress="00:11:22:33:44:55")

    # Test missing name
    with pytest.raises(ValueError, match="Missing required fields for create: name"):
        resource.create(
            "venue_1", serialNumber="ABC123", macAddress="00:11:22:33:44:55"
        )

    # Test missing both
    with pytest.raises(ValueError, match="Missing required fields for create"):
        resource.create("venue_1", macAddress="00:11:22:33:44:55")


def test_aps_update(mock_client):
    """Test updating an AP."""
    mock_client.put.return_value = {"serialNumber": "ABC123", "name": "Updated AP"}

    resource = APsResource(mock_client)
    ap = resource.update("venue_1", "ABC123", {"name": "Updated AP"})

    assert ap["name"] == "Updated AP"
    mock_client.put.assert_called_once()


def test_aps_delete(mock_client):
    """Test deleting an AP."""
    mock_client.delete.return_value = {"requestId": "req_123"}

    resource = APsResource(mock_client)
    result = resource.delete("venue_1", "ABC123")

    assert result == {"requestId": "req_123"}
    mock_client.delete.assert_called_once_with("/venues/aps", json=["ABC123"])


def test_aps_get_lldp_neighbors(mock_client):
    """Test getting AP LLDP neighbors."""
    mock_client.post.return_value = {
        "data": [
            {
                "deviceName": "Switch1",
                "interface": "GigabitEthernet0/1",
                "chassisId": "00:11:22:33:44:55",
            }
        ]
    }

    resource = APsResource(mock_client)
    neighbors = resource.get_lldp_neighbors("venue_1", "ABC123")

    assert len(neighbors) == 1
    assert neighbors[0]["deviceName"] == "Switch1"
    mock_client.post.assert_called_once_with(
        "/venues/venue_1/aps/ABC123/neighbors/query",
        json={
            "filters": [{"type": "LLDP_NEIGHBOR"}],
            "page": 1,
            "pageSize": 25,
            "sortOrder": "ASC",
        },
    )


def test_aps_get_lldp_neighbors_empty(mock_client):
    """Test getting AP LLDP neighbors when none exist."""
    mock_client.post.return_value = None

    resource = APsResource(mock_client)
    neighbors = resource.get_lldp_neighbors("venue_1", "ABC123")

    assert neighbors == []


def test_aps_get_lldp_neighbors_with_pagination(mock_client):
    """Test getting AP LLDP neighbors with pagination parameters."""
    mock_client.post.return_value = {
        "data": [
            {
                "deviceName": "Switch1",
                "interface": "GigabitEthernet0/1",
                "chassisId": "00:11:22:33:44:55",
            }
        ]
    }

    resource = APsResource(mock_client)
    neighbors = resource.get_lldp_neighbors("venue_1", "ABC123", page=2, page_size=50)

    assert len(neighbors) == 1
    mock_client.post.assert_called_once_with(
        "/venues/venue_1/aps/ABC123/neighbors/query",
        json={
            "filters": [{"type": "LLDP_NEIGHBOR"}],
            "page": 2,
            "pageSize": 50,
            "sortOrder": "ASC",
        },
    )


def test_aps_get_lldp_neighbors_with_sorting(mock_client):
    """Test getting AP LLDP neighbors with sorting parameters."""
    mock_client.post.return_value = {
        "data": [
            {
                "deviceName": "Switch1",
                "interface": "GigabitEthernet0/1",
                "chassisId": "00:11:22:33:44:55",
            }
        ]
    }

    resource = APsResource(mock_client)
    neighbors = resource.get_lldp_neighbors(
        "venue_1", "ABC123", sort_field="deviceName", sort_order="DESC"
    )

    assert len(neighbors) == 1
    mock_client.post.assert_called_once_with(
        "/venues/venue_1/aps/ABC123/neighbors/query",
        json={
            "filters": [{"type": "LLDP_NEIGHBOR"}],
            "page": 1,
            "pageSize": 25,
            "sortField": "deviceName",
            "sortOrder": "DESC",
        },
    )


def test_aps_get_lldp_neighbors_list_response(mock_client):
    """Test getting AP LLDP neighbors with list response."""
    mock_client.post.return_value = [
        {
            "deviceName": "Switch1",
            "interface": "GigabitEthernet0/1",
            "chassisId": "00:11:22:33:44:55",
        }
    ]

    resource = APsResource(mock_client)
    neighbors = resource.get_lldp_neighbors("venue_1", "ABC123")

    assert len(neighbors) == 1
    assert neighbors[0]["deviceName"] == "Switch1"


def test_aps_collect_neighbors(mock_client):
    """Test triggering neighbor collection for an AP."""
    mock_client.patch.return_value = {"requestId": "req_123", "status": "ACCEPTED"}

    resource = APsResource(mock_client)
    result = resource.collect_neighbors("venue_1", "ABC123")

    assert result["requestId"] == "req_123"
    mock_client.patch.assert_called_once_with(
        "/venues/venue_1/aps/ABC123/neighbors",
        json={"status": "CURRENT", "type": "LLDP_NEIGHBOR"},
    )


def test_aps_collect_neighbors_rf_type(mock_client):
    """Test triggering RF neighbor collection."""
    mock_client.patch.return_value = {"requestId": "req_123"}

    resource = APsResource(mock_client)
    result = resource.collect_neighbors(
        "venue_1", "ABC123", neighbor_type="RF_NEIGHBOR"
    )

    mock_client.patch.assert_called_once_with(
        "/venues/venue_1/aps/ABC123/neighbors",
        json={"status": "CURRENT", "type": "RF_NEIGHBOR"},
    )


def test_aps_get_lldp_neighbors_no_data_error(mock_client):
    """Test getting AP LLDP neighbors when API returns no data error."""
    from ruckus_one.exceptions import RuckusOneAPIError

    # Mock the 400 error with WIFI-10498 code
    mock_client.post.side_effect = RuckusOneAPIError(
        "No detected neighbor data.",
        status_code=400,
        response_data={
            "requestId": "test-request-id",
            "errors": [
                {
                    "code": "WIFI-10498",
                    "message": "No detected neighbor data.",
                    "reason": "Investigate to detect neighbor data.",
                }
            ],
        },
    )

    resource = APsResource(mock_client)
    neighbors = resource.get_lldp_neighbors("venue_1", "ABC123")

    # Should return empty list instead of raising
    assert neighbors == []


def test_aps_get_lldp_neighbors_with_neighbors_field(mock_client):
    """Test getting AP LLDP neighbors with neighbors field in response."""
    mock_client.post.return_value = {
        "neighbors": [
            {
                "deviceName": "Switch1",
                "interface": "GigabitEthernet0/1",
                "chassisId": "00:11:22:33:44:55",
            }
        ],
        "page": 1,
        "totalCount": 1,
        "totalPages": 1,
    }

    resource = APsResource(mock_client)
    neighbors = resource.get_lldp_neighbors("venue_1", "ABC123")

    assert len(neighbors) == 1
    assert neighbors[0]["deviceName"] == "Switch1"
