"""Tests for DpskServicesResource."""

import pytest

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.dpsk_services import DpskServicesResource


def test_dpsk_services_list_pagination_totalCount_dict_shape(mock_client):
    resource = DpskServicesResource(mock_client)

    mock_client.post.side_effect = [
        {
            "data": [
                {
                    "id": "d1",
                    "name": "Pool-A",
                    "passphraseFormat": "KEYBOARD_FRIENDLY",
                    "networkCount": 2,
                },
                {
                    "id": "d2",
                    "name": "Pool-B",
                    "passphraseFormat": "KEYBOARD_FRIENDLY",
                    "networkCount": 1,
                },
            ],
            "totalCount": 4,
        },
        {
            "data": [],
            "totalCount": 4,
        },
    ]

    pools = resource.list(page_size=2)
    assert len(pools) == 2
    assert pools[0]["id"] == "d1"
    assert pools[1]["id"] == "d2"

    assert mock_client.post.call_count == 2

    first_call = mock_client.post.call_args_list[0]
    assert first_call.args[0] == "/dpskServices/query"
    assert first_call.kwargs["json"]["page"] == 1
    assert first_call.kwargs["json"]["pageSize"] == 2
    assert first_call.kwargs["json"]["fields"] == [
        "id",
        "name",
        "passphraseFormat",
        "networkCount",
    ]


def test_dpsk_services_list_bare_list_response(mock_client):
    resource = DpskServicesResource(mock_client)

    mock_client.post.return_value = [{"id": "d1", "name": "Pool-A"}]
    pools = resource.list(page_size=50)

    assert pools == [{"id": "d1", "name": "Pool-A"}]
    assert mock_client.post.call_count == 1


def test_dpsk_services_get_by_name_success(mock_client):
    resource = DpskServicesResource(mock_client)

    mock_client.get.return_value = {
        "content": [
            {
                "id": "d1",
                "name": "Local-Services-DPSK",
                "passphraseFormat": "KEYBOARD_FRIENDLY",
                "passphraseLength": 12,
                "networkCount": 2,
            }
        ]
    }

    profile = resource.get_by_name("Local-Services-DPSK")
    assert profile["id"] == "d1"
    assert profile["name"] == "Local-Services-DPSK"

    call = mock_client.get.call_args
    assert call.args[0] == "/dpskServices"
    assert call.kwargs["params"] == {"name": "Local-Services-DPSK"}

    # Default behavior should return the full object (not projected down).
    assert profile["passphraseLength"] == 12


def test_dpsk_services_get_by_name_not_found(mock_client):
    resource = DpskServicesResource(mock_client)

    mock_client.get.return_value = {"content": []}

    with pytest.raises(RuckusOneNotFoundError):
        resource.get_by_name("MissingPool")


def test_dpsk_services_get_by_name_multiple_matches(mock_client):
    resource = DpskServicesResource(mock_client)

    mock_client.get.return_value = {
        "content": [
            {"id": "d1", "name": "Pool", "passphraseFormat": "KEYBOARD_FRIENDLY"},
            {"id": "d2", "name": "Pool", "passphraseFormat": "KEYBOARD_FRIENDLY"},
        ]
    }

    with pytest.raises(ValueError):
        resource.get_by_name("Pool")
