"""Tests for venues resource."""

from unittest.mock import MagicMock, patch

import pytest

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.venues import VenuesResource


def test_venues_resource_initialization(mock_client):
    """Test VenuesResource initialization."""
    resource = VenuesResource(mock_client)
    assert resource.client == mock_client
    assert resource.path == "/venues"


def test_venues_all(mock_client):
    """Test listing all venues uses POST /venues/query, never GET /venues."""
    mock_client.post.return_value = {
        "totalCount": 1,
        "page": 1,
        "data": [{"id": "1", "name": "Venue 1"}],
    }

    resource = VenuesResource(mock_client)
    venues = resource.all()

    assert len(venues) == 1
    assert venues[0]["name"] == "Venue 1"
    mock_client.post.assert_called_once_with(
        "/venues/query", json={"page": 1, "pageSize": 100}
    )
    mock_client.get.assert_not_called()


def test_venues_all_paginates(mock_client):
    """Test all() requests further pages until totalCount is reached."""
    page_size = VenuesResource._QUERY_PAGE_SIZE
    first = [{"id": str(i), "name": f"Venue {i}"} for i in range(page_size)]
    second = [{"id": "last", "name": "Last Venue"}]
    mock_client.post.side_effect = [
        {"totalCount": page_size + 1, "page": 1, "data": first},
        {"totalCount": page_size + 1, "page": 2, "data": second},
    ]

    resource = VenuesResource(mock_client)
    venues = resource.all()

    assert len(venues) == page_size + 1
    assert venues[-1]["id"] == "last"
    assert [c.kwargs["json"]["page"] for c in mock_client.post.call_args_list] == [
        1,
        2,
    ]


def test_venues_all_stops_at_total_count_on_full_page(mock_client):
    """Test all() stops when a full page brings the count to totalCount."""
    page_size = VenuesResource._QUERY_PAGE_SIZE
    full = [{"id": str(i), "name": f"Venue {i}"} for i in range(page_size)]
    mock_client.post.return_value = {"totalCount": page_size, "data": full}

    resource = VenuesResource(mock_client)
    venues = resource.all()

    assert len(venues) == page_size
    mock_client.post.assert_called_once()


def test_venues_all_empty(mock_client):
    """Test all() returns an empty list when the query returns nothing."""
    mock_client.post.return_value = None

    resource = VenuesResource(mock_client)

    assert resource.all() == []


def test_venues_get_by_id(mock_client):
    """Test getting venue by ID."""
    mock_client.get.return_value = {"id": "1", "name": "Venue 1"}

    resource = VenuesResource(mock_client)
    venue = resource.get(id="1")

    assert venue["id"] == "1"
    assert venue["name"] == "Venue 1"


def test_venues_get_by_id_not_found(mock_client):
    """Test getting venue by ID when not found."""
    mock_client.get.return_value = None

    resource = VenuesResource(mock_client)
    with pytest.raises(RuckusOneNotFoundError):
        resource.get(id="999")


def test_venues_get_by_name(mock_client):
    """Test get_by_name resolves the ID by query, then fetches the venue."""
    mock_client.post.return_value = {
        "totalCount": 1,
        "data": [{"id": "1", "name": "Test Venue"}],
    }
    mock_client.get.return_value = {
        "id": "1",
        "name": "Test Venue",
        "address": {"city": "Test City"},
    }

    resource = VenuesResource(mock_client)
    venue = resource.get_by_name("Test Venue")

    assert venue["name"] == "Test Venue"
    assert venue["address"] == {"city": "Test City"}
    assert resource._name_cache["Test Venue"] == "1"


def test_venues_get_name_uses_exact_query_filter(mock_client):
    """Test get(name=...) sends a filters.name query and GETs the venue by ID."""
    mock_client.post.return_value = {
        "totalCount": 1,
        "data": [{"id": "abc", "name": "BUTLSKEG"}],
    }
    mock_client.get.return_value = {"id": "abc", "name": "BUTLSKEG"}

    resource = VenuesResource(mock_client)
    venue = resource.get(name="BUTLSKEG")

    assert venue == {"id": "abc", "name": "BUTLSKEG"}
    mock_client.post.assert_called_once_with(
        "/venues/query",
        json={
            "page": 1,
            "pageSize": 100,
            "fields": ["id", "name"],
            "filters": {"name": ["BUTLSKEG"]},
        },
    )
    mock_client.get.assert_called_once_with("/venues/abc")


def test_venues_get_name_not_found(mock_client):
    """Test get(name=...) raises NotFound when the query has no match."""
    mock_client.post.return_value = {"totalCount": 0, "page": 1, "data": []}

    resource = VenuesResource(mock_client)
    with pytest.raises(RuckusOneNotFoundError):
        resource.get(name="Missing")
    mock_client.get.assert_not_called()


def test_venues_get_name_multiple_matches(mock_client):
    """Test get(name=...) raises ValueError when the query matches twice."""
    mock_client.post.return_value = {
        "totalCount": 2,
        "data": [{"id": "1", "name": "Dup"}, {"id": "2", "name": "Dup"}],
    }

    resource = VenuesResource(mock_client)
    with pytest.raises(ValueError, match="Multiple venues"):
        resource.get(name="Dup")
    mock_client.get.assert_not_called()


def test_venues_get_name_match_without_id(mock_client):
    """Test get(name=...) raises ValueError when the match carries no id."""
    mock_client.post.return_value = {"totalCount": 1, "data": [{"name": "NoId"}]}

    resource = VenuesResource(mock_client)
    with pytest.raises(ValueError, match="has no id"):
        resource.get(name="NoId")


def test_venues_get_other_filters_use_query_listing(mock_client):
    """Test get() with non-name filters filters all() results client-side."""
    mock_client.post.return_value = {
        "totalCount": 2,
        "data": [
            {"id": "1", "name": "A", "countryCode": "GB"},
            {"id": "2", "name": "B", "countryCode": "IE"},
        ],
    }

    resource = VenuesResource(mock_client)
    venue = resource.get(countryCode="IE")

    assert venue["id"] == "2"
    mock_client.post.assert_called_once_with(
        "/venues/query", json={"page": 1, "pageSize": 100}
    )
    mock_client.get.assert_not_called()


def test_venues_create(mock_client):
    """Test creating a venue."""
    mock_client.post.return_value = {"id": "1", "name": "New Venue"}

    resource = VenuesResource(mock_client)
    address = {
        "addressLine": "123 Test St",
        "city": "Test City",
        "country": "United States",
        "countryCode": "US",
    }
    venue = resource.create(name="New Venue", address=address)

    assert venue["name"] == "New Venue"
    mock_client.post.assert_called_once_with(
        "/venues", json={"name": "New Venue", "address": address}
    )


def test_venues_create_missing_required_field(mock_client):
    """Test creating a venue without required fields."""
    resource = VenuesResource(mock_client)

    # Missing name
    with pytest.raises(ValueError, match="Missing required fields for create: name"):
        resource.create(address={"addressLine": "123 Test St"})

    # Missing address
    with pytest.raises(ValueError, match="Missing required fields for create: address"):
        resource.create(name="Test Venue")

    # Missing both
    with pytest.raises(
        ValueError, match="Missing required fields for create: name, address"
    ):
        resource.create()


def test_venues_create_invalid_address_type(mock_client):
    """Test creating a venue with invalid address type."""
    resource = VenuesResource(mock_client)

    # Address as string instead of dict
    with pytest.raises(ValueError, match="address must be a dictionary, got str"):
        resource.create(name="Test Venue", address="123 Test St")

    # Address as list instead of dict
    with pytest.raises(ValueError, match="address must be a dictionary, got list"):
        resource.create(name="Test Venue", address=["123 Test St"])


def test_venues_create_valid_country_name(mock_client):
    """Test creating a venue with valid country name."""
    mock_client.post.return_value = {"id": "1", "name": "New Venue"}

    resource = VenuesResource(mock_client)
    address = {
        "addressLine": "123 Test St",
        "city": "London",
        "country": "United Kingdom",
    }
    venue = resource.create(name="New Venue", address=address)

    assert venue["name"] == "New Venue"
    mock_client.post.assert_called_once_with(
        "/venues", json={"name": "New Venue", "address": address}
    )


def test_venues_create_country_name_case_insensitive(mock_client):
    """Test that country name validation is case-insensitive."""
    mock_client.post.return_value = {"id": "1", "name": "New Venue"}

    resource = VenuesResource(mock_client)
    # Test various case combinations
    for country in [
        "united kingdom",
        "UNITED KINGDOM",
        "United Kingdom",
        "UnItEd KiNgDoM",
    ]:
        address = {
            "city": "London",
            "country": country,
        }
        venue = resource.create(name="New Venue", address=address)
        assert venue["name"] == "New Venue"


def test_venues_create_reject_iso_alpha2_code(mock_client):
    """Test that ISO alpha-2 codes are rejected."""
    resource = VenuesResource(mock_client)

    address = {
        "city": "London",
        "country": "GB",
    }
    with pytest.raises(ValueError, match="Country code 'GB' is not accepted"):
        resource.create(name="Test Venue", address=address)


def test_venues_create_reject_iso_alpha3_code(mock_client):
    """Test that ISO alpha-3 codes are rejected."""
    resource = VenuesResource(mock_client)

    address = {
        "city": "London",
        "country": "GBR",
    }
    with pytest.raises(ValueError, match="Country code 'GBR' is not accepted"):
        resource.create(name="Test Venue", address=address)


def test_venues_create_reject_lowercase_iso_code(mock_client):
    """Test that lowercase ISO codes are also rejected."""
    resource = VenuesResource(mock_client)

    address = {
        "city": "London",
        "country": "gb",  # lowercase
    }
    with pytest.raises(ValueError, match="Country code 'gb' is not accepted"):
        resource.create(name="Test Venue", address=address)


def test_venues_create_invalid_country_name(mock_client):
    """Test that invalid country names are rejected."""
    resource = VenuesResource(mock_client)

    address = {
        "city": "London",
        "country": "xyz",
    }
    with pytest.raises(ValueError, match="Invalid country name 'xyz'"):
        resource.create(name="Test Venue", address=address)


def test_venues_create_country_typo_rejected(mock_client):
    """Test that typos in country names are rejected."""
    resource = VenuesResource(mock_client)

    address = {
        "city": "London",
        "country": "United Kingdon",  # Typo: missing 'm'
    }
    with pytest.raises(ValueError, match="Invalid country name 'United Kingdon'"):
        resource.create(name="Test Venue", address=address)


def test_venues_update(mock_client):
    """Test updating a venue."""
    mock_client.put.return_value = {"id": "1", "name": "Updated Venue"}

    resource = VenuesResource(mock_client)
    venue = resource.update("1", {"name": "Updated Venue"})

    assert venue["name"] == "Updated Venue"
    mock_client.put.assert_called_once_with("/venues/1", json={"name": "Updated Venue"})


def test_venues_filter(mock_client):
    """Test filtering venues."""
    mock_client.post.return_value = {"data": [{"id": "1", "name": "Test Venue"}]}

    resource = VenuesResource(mock_client)
    venues = resource.filter(name="Test")

    assert len(venues) == 1
    assert venues[0]["name"] == "Test Venue"


def test_venues_delete(mock_client):
    """Test deleting a venue."""
    mock_client.delete.return_value = {"requestId": "req_123"}

    resource = VenuesResource(mock_client)
    result = resource.delete("venue_1")

    assert result == {"requestId": "req_123"}
    mock_client.delete.assert_called_once_with("/venues", json=["venue_1"])


def test_venues_delete_multiple(mock_client):
    """Test deleting multiple venues."""
    mock_client.delete.return_value = {"requestId": "req_123"}

    resource = VenuesResource(mock_client)
    result = resource.delete(["venue_1", "venue_2"])

    assert result == {"requestId": "req_123"}
    mock_client.delete.assert_called_once_with("/venues", json=["venue_1", "venue_2"])


def test_venues_filter_with_query_fallback(mock_client):
    """Test filter method with POST /query fallback to GET."""
    resource = VenuesResource(mock_client)

    # Test when POST /query raises NotFoundError, falls back to GET
    mock_client.post.side_effect = RuckusOneNotFoundError("Not found")
    mock_client.get.return_value = {"data": [{"id": "1", "name": "Venue 1"}]}

    result = resource.filter(name="Venue 1")
    assert result == [{"id": "1", "name": "Venue 1"}]
    mock_client.post.assert_called_once_with("/venues/query", json={"name": "Venue 1"})
    mock_client.get.assert_called_once_with("/venues", params={"name": "Venue 1"})


def test_venues_filter_with_list_response(mock_client):
    """Test filter method when response is a list."""
    resource = VenuesResource(mock_client)

    # Test when POST /query returns a list directly
    mock_client.post.return_value = [{"id": "1", "name": "Venue 1"}]

    result = resource.filter(name="Venue 1")
    assert result == [{"id": "1", "name": "Venue 1"}]


def test_venues_filter_with_empty_response(mock_client):
    """Test filter method when response is None."""
    resource = VenuesResource(mock_client)

    mock_client.post.return_value = None

    result = resource.filter(name="Venue 1")
    assert result == []


def test_venues_create_with_empty_string_field(mock_client):
    """Test create validation with empty string field."""
    resource = VenuesResource(mock_client)

    # Empty string should be treated as missing
    with pytest.raises(ValueError, match="Missing required fields for create: name"):
        resource.create(name="", address={"country": "United States"})


def test_venues_create_with_empty_list_field(mock_client):
    """Test create validation with empty list field."""
    resource = VenuesResource(mock_client)

    # Empty list should be treated as missing
    with pytest.raises(ValueError, match="Missing required fields for create"):
        resource.create(name="Test", tags=[])


def test_venues_create_with_empty_dict_field(mock_client):
    """Test create validation with empty dict field (should pass through)."""
    resource = VenuesResource(mock_client)

    # Empty dict should pass through (let API validate)
    mock_client.post.return_value = {"id": "1", "name": "Test", "address": {}}
    result = resource.create(name="Test", address={})
    assert result == {"id": "1", "name": "Test", "address": {}}


def test_venues_create_with_none_response(mock_client):
    """Test create method when response is None."""
    resource = VenuesResource(mock_client)

    mock_client.post.return_value = None

    with pytest.raises(ValueError, match="Failed to create item"):
        resource.create(name="Test", address={"country": "United States"})
