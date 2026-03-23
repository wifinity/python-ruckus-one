"""Tests for RadiusServerProfilesResource."""

import pytest

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.radius_server_profiles import (
    RadiusServerProfilesResource,
)


def test_radius_server_profiles_list_pagination_dict_shape(mock_client):
    resource = RadiusServerProfilesResource(mock_client)

    mock_client.post.side_effect = [
        {
            "data": [
                {"id": "r1", "name": "A", "primary": True, "type": "pap"},
                {"id": "r2", "name": "B", "primary": False, "type": "chap"},
            ],
            # Use a total greater than the items returned so the
            # implementation doesn't stop early based on meta.total.
            "meta": {"total": 10},
        },
        {
            "data": [],
            "meta": {"total": 10},
        },
    ]

    profiles = resource.list(page_size=2)
    assert len(profiles) == 2
    assert profiles[0]["name"] == "A"
    assert profiles[1]["name"] == "B"

    assert mock_client.post.call_count == 2

    first_call = mock_client.post.call_args_list[0]
    assert first_call.args[0] == "/radiusServerProfiles/query"
    assert first_call.kwargs["json"]["page"] == 1
    assert first_call.kwargs["json"]["pageSize"] == 2
    assert first_call.kwargs["json"]["fields"] == ["id", "name", "primary", "type"]

    second_call = mock_client.post.call_args_list[1]
    assert second_call.args[0] == "/radiusServerProfiles/query"
    assert second_call.kwargs["json"]["page"] == 2
    assert second_call.kwargs["json"]["pageSize"] == 2


def test_radius_server_profiles_list_bare_list_response(mock_client):
    resource = RadiusServerProfilesResource(mock_client)

    mock_client.post.return_value = [{"id": "r1", "name": "A"}]
    profiles = resource.list(page_size=50)
    assert profiles == [{"id": "r1", "name": "A"}]
    assert mock_client.post.call_count == 1


def test_radius_server_profiles_get_by_name_success(mock_client):
    resource = RadiusServerProfilesResource(mock_client)

    mock_client.post.return_value = {
        "data": [{"id": "r1", "name": "NPS", "primary": True, "type": "pap"}],
        "meta": {"total": 1},
    }

    profile = resource.get_by_name("NPS")
    assert profile["id"] == "r1"
    assert profile["name"] == "NPS"

    call = mock_client.post.call_args
    assert call.args[0] == "/radiusServerProfiles/query"

    body = call.kwargs["json"]
    assert body["page"] == 1
    assert body["pageSize"] == 50
    assert body["matchFields"] == [{"field": "name", "value": "NPS"}]
    assert body["fields"] == ["id", "name", "primary", "type"]


def test_radius_server_profiles_get_by_name_not_found(mock_client):
    resource = RadiusServerProfilesResource(mock_client)

    mock_client.post.return_value = {"data": []}

    with pytest.raises(RuckusOneNotFoundError):
        resource.get_by_name("MissingProfile")


def test_radius_server_profiles_get_by_name_multiple_matches(mock_client):
    resource = RadiusServerProfilesResource(mock_client)

    mock_client.post.return_value = {
        "data": [
            {"id": "r1", "name": "NPS"},
            {"id": "r2", "name": "NPS"},
        ]
    }

    with pytest.raises(ValueError):
        resource.get_by_name("NPS")
