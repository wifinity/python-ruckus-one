"""Tests for APs resource."""

from unittest.mock import MagicMock, call

import pytest

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.aps import APsResource


def test_aps_resource_initialization(mock_client):
    """Test APsResource initialization."""
    resource = APsResource(mock_client)
    assert resource.client == mock_client


LOOKUP_FIELDS = ["serialNumber", "name", "venueId", "apGroupId", "model"]


def lookup_call(serials):
    return call(
        "/venues/aps/query",
        json={
            "fields": LOOKUP_FIELDS,
            "filters": {"serialNumber": serials},
            "page": 1,
            "pageSize": 100,
        },
    )


def test_aps_get_by_serial(mock_client):
    """get_by_serial() finds the AP's venue by query, then reads its configuration."""
    mock_client.post.return_value = {
        "data": [
            {
                "serialNumber": "ABC123",
                "name": "AP query name",
                "venueId": "venue_1",
                "apGroupId": "grp-1",
            }
        ],
        "totalCount": 1,
    }
    mock_client.get.return_value = {
        "name": "Lobby AP",
        "description": "Ground floor",
        "tags": ["t"],
    }

    resource = APsResource(mock_client)
    ap = resource.get_by_serial("venue_1", "ABC123")

    assert ap == {
        "serialNumber": "ABC123",
        "name": "Lobby AP",
        "description": "Ground floor",
        "tags": ["t"],
        "venueId": "venue_1",
        "apGroupId": "grp-1",
    }
    assert mock_client.post.call_args_list == [lookup_call(["ABC123"])]
    mock_client.get.assert_called_once_with("/venues/venue_1/aps/ABC123")


def test_aps_get_by_serial_reports_the_venue_the_ap_is_in(mock_client):
    """An AP registered in another venue is found there, and venueId says so."""
    mock_client.post.return_value = {
        "data": [{"serialNumber": "ABC123", "venueId": "venue_other"}]
    }
    mock_client.get.return_value = {"name": "AP"}

    ap = APsResource(mock_client).get_by_serial("venue_1", "ABC123")

    assert ap["venueId"] == "venue_other"
    mock_client.get.assert_called_once_with("/venues/venue_other/aps/ABC123")


def test_aps_get_by_serial_ignores_other_serials(mock_client):
    """A query row for a different serial is not taken as a match."""
    mock_client.post.return_value = {
        "data": [{"serialNumber": "ZZZ999", "venueId": "venue_1"}]
    }

    with pytest.raises(RuckusOneNotFoundError):
        APsResource(mock_client).get_by_serial("venue_1", "ABC123")
    mock_client.get.assert_not_called()


def test_aps_get_by_serial_not_found(mock_client):
    """Test getting AP by serial when not found."""
    mock_client.post.return_value = {"data": [], "totalCount": 0}

    resource = APsResource(mock_client)
    with pytest.raises(RuckusOneNotFoundError):
        resource.get_by_serial("venue_1", "INVALID")


def test_aps_get_by_serial_detail_empty(mock_client):
    mock_client.post.return_value = {"data": [{"serialNumber": "A", "venueId": "v"}]}
    mock_client.get.return_value = None

    with pytest.raises(RuckusOneNotFoundError):
        APsResource(mock_client).get_by_serial("v", "A")


def test_aps_list(mock_client):
    """list() pages through POST /venues/aps/query filtered on the venue."""
    mock_client.post.return_value = {
        "data": [{"serialNumber": "ABC123"}, {"serialNumber": "DEF456"}],
        "totalCount": 2,
    }

    resource = APsResource(mock_client)
    aps = resource.list("venue_1")

    assert len(aps) == 2
    assert aps[0]["serialNumber"] == "ABC123"
    mock_client.post.assert_called_once_with(
        "/venues/aps/query",
        json={"filters": {"venueId": ["venue_1"]}, "page": 1, "pageSize": 100},
    )
    mock_client.get.assert_not_called()


def test_aps_list_keyword_filters_become_query_filters(mock_client):
    mock_client.post.return_value = {"data": []}

    APsResource(mock_client).list(serialNumber="A1", apGroupId=["g1", "g2"])

    mock_client.post.assert_called_once_with(
        "/venues/aps/query",
        json={
            "filters": {"serialNumber": ["A1"], "apGroupId": ["g1", "g2"]},
            "page": 1,
            "pageSize": 100,
        },
    )


def test_aps_list_without_filters(mock_client):
    mock_client.post.return_value = {"data": [{"serialNumber": "A"}]}

    assert APsResource(mock_client).list() == [{"serialNumber": "A"}]
    mock_client.post.assert_called_once_with(
        "/venues/aps/query", json={"page": 1, "pageSize": 100}
    )


def test_aps_create(mock_client):
    """create() posts a single AP object to /venues/{venueId}/aps."""
    mock_client.post.return_value = {"requestId": "req_1", "response": {"id": "x"}}

    resource = APsResource(mock_client)
    result = resource.create(
        "venue_1",
        serialNumber="ABC123",
        name="Test AP",
        description="d",
        venueId="ignored",
    )

    assert result == {"requestId": "req_1", "response": {"id": "x"}}
    mock_client.post.assert_called_once_with(
        "/venues/venue_1/aps",
        json={"serialNumber": "ABC123", "name": "Test AP", "description": "d"},
    )


def test_aps_create_empty_response(mock_client):
    mock_client.post.return_value = None

    with pytest.raises(ValueError, match="Failed to create AP"):
        APsResource(mock_client).create("v", serialNumber="A", name="n")


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
    """delete() deletes the AP in the venue the query reports for it."""
    mock_client.post.return_value = {
        "data": [{"serialNumber": "ABC123", "venueId": "venue_1"}]
    }
    mock_client.delete.return_value = {"requestId": "req_123"}

    resource = APsResource(mock_client)
    result = resource.delete("venue_1", "ABC123")

    assert result == {"requestId": "req_123"}
    assert mock_client.post.call_args_list == [lookup_call(["ABC123"])]
    mock_client.delete.assert_called_once_with("/venues/venue_1/aps/ABC123")


def test_aps_delete_ap_in_another_venue(mock_client):
    mock_client.post.return_value = {
        "data": [{"serialNumber": "ABC123", "venueId": "venue_other"}]
    }
    mock_client.delete.return_value = {"requestId": "req_1"}

    APsResource(mock_client).delete("venue_1", "ABC123")

    mock_client.delete.assert_called_once_with("/venues/venue_other/aps/ABC123")


def test_aps_delete_list(mock_client):
    """A list deletes each AP and returns one response per serial."""
    mock_client.post.return_value = {
        "data": [{"serialNumber": "A", "venueId": "venue_a"}]
    }
    mock_client.delete.side_effect = [{"requestId": "r1"}, {"requestId": "r2"}]

    result = APsResource(mock_client).delete("venue_1", ["A", "B"])

    assert result == {"responses": [{"requestId": "r1"}, {"requestId": "r2"}]}
    assert mock_client.post.call_args_list == [lookup_call(["A", "B"])]
    assert mock_client.delete.call_args_list == [
        call("/venues/venue_a/aps/A"),
        call("/venues/venue_1/aps/B"),
    ]


def test_aps_delete_empty_list(mock_client):
    assert APsResource(mock_client).delete("venue_1", []) == {"responses": []}
    mock_client.post.assert_not_called()
    mock_client.delete.assert_not_called()


def test_aps_delete_invalid_type(mock_client):
    with pytest.raises(ValueError, match="serial_number must be"):
        APsResource(mock_client).delete("venue_1", 123)  # type: ignore[arg-type]


def test_aps_move(mock_client):
    """move() reads the AP, deletes it from its venue and creates it in the target."""
    mock_client.post.side_effect = [
        {"data": [{"serialNumber": "A", "venueId": "v1"}]},
        {"data": [{"serialNumber": "A", "venueId": "v1"}]},
        {"requestId": "req_create"},
    ]
    mock_client.get.return_value = {"name": "AP", "description": "d", "model": "R1"}
    mock_client.delete.return_value = {"requestId": "req_delete"}

    result = APsResource(mock_client).move("v1", "A", "v2")

    assert result == {"requestId": "req_create"}
    mock_client.delete.assert_called_once_with("/venues/v1/aps/A")
    assert mock_client.post.call_args_list[-1] == call(
        "/venues/v2/aps", json={"name": "AP", "description": "d", "serialNumber": "A"}
    )


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


def test_aps_get_network_settings(mock_client):
    """Test getting AP network settings."""
    mock_client.get.return_value = {
        "ipType": "STATIC",
        "ip": "192.168.1.10",
        "netmask": "255.255.255.0",
        "gateway": "192.168.1.1",
        "primaryDnsServer": "8.8.8.8",
        "secondaryDnsServer": "8.8.4.4",
    }

    resource = APsResource(mock_client)
    settings = resource.get_network_settings("venue_1", "ABC123")

    assert settings["ipType"] == "STATIC"
    assert settings["ip"] == "192.168.1.10"
    mock_client.get.assert_called_once_with(
        "/venues/venue_1/aps/ABC123/networkSettings"
    )


def test_aps_get_network_settings_empty_response(mock_client):
    """Test getting AP network settings when API returns no response."""
    mock_client.get.return_value = None

    resource = APsResource(mock_client)
    settings = resource.get_network_settings("venue_1", "ABC123")

    assert settings == {}


def test_aps_update_network_settings(mock_client):
    """Test updating AP network settings."""
    settings = {
        "ipType": "STATIC",
        "ip": "192.168.1.10",
        "netmask": "255.255.255.0",
        "gateway": "192.168.1.1",
        "primaryDnsServer": "8.8.8.8",
        "secondaryDnsServer": "8.8.4.4",
    }
    mock_client.put.return_value = settings

    resource = APsResource(mock_client)
    result = resource.update_network_settings("venue_1", "ABC123", settings)

    assert result == settings
    mock_client.put.assert_called_once_with(
        "/venues/venue_1/aps/ABC123/networkSettings", json=settings
    )


def test_aps_update_network_settings_failure(mock_client):
    """Test updating AP network settings when API returns no response."""
    mock_client.put.return_value = None

    resource = APsResource(mock_client)
    with pytest.raises(ValueError, match="Failed to update network settings"):
        resource.update_network_settings(
            "venue_1", "ABC123", {"ipType": "STATIC", "ip": "192.168.1.10"}
        )
