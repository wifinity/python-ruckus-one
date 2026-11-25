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


SEARCH_BODY = {
    "searchString": "Local-Services-DPSK",
    "searchTargetFields": ["name"],
    "page": 1,
    "pageSize": 100,
}


def test_dpsk_services_get_by_name_success(mock_client):
    """get_by_name() searches POST /dpskServices/query and keeps the exact match."""
    resource = DpskServicesResource(mock_client)

    mock_client.post.return_value = {
        "data": [
            {"id": "d0", "name": "Local-Services-DPSK-2"},
            {
                "id": "d1",
                "name": "Local-Services-DPSK",
                "passphraseFormat": "KEYBOARD_FRIENDLY",
                "passphraseLength": 12,
                "networkCount": 2,
            },
        ],
        "totalCount": 2,
    }

    profile = resource.get_by_name("Local-Services-DPSK")
    assert profile["id"] == "d1"
    assert profile["name"] == "Local-Services-DPSK"
    assert profile["passphraseLength"] == 12

    mock_client.post.assert_called_once_with("/dpskServices/query", json=SEARCH_BODY)
    mock_client.get.assert_not_called()


def test_dpsk_services_get_by_name_projects_fields(mock_client):
    mock_client.post.return_value = {
        "data": [{"id": "d1", "name": "Pool", "passphraseLength": 12}]
    }

    profile = DpskServicesResource(mock_client).get_by_name("Pool", fields=["id"])

    assert profile == {"id": "d1"}


def test_dpsk_services_get_by_name_follows_pages(mock_client):
    """The search pages until the exact match is found or rows run out."""
    first = {"data": [{"id": str(i), "name": f"Pool {i}"} for i in range(100)]}
    second = {"data": [{"id": "x", "name": "Pool"}]}
    mock_client.post.side_effect = [first, second]

    profile = DpskServicesResource(mock_client).get_by_name("Pool")

    assert profile["id"] == "x"
    assert mock_client.post.call_args_list[1].kwargs["json"]["page"] == 2


def test_dpsk_services_get_by_name_not_found(mock_client):
    resource = DpskServicesResource(mock_client)

    mock_client.post.return_value = {"data": [{"id": "d1", "name": "MissingPool 2"}]}

    with pytest.raises(RuckusOneNotFoundError):
        resource.get_by_name("MissingPool")


def test_dpsk_services_get_by_name_is_case_sensitive(mock_client):
    mock_client.post.return_value = {"data": [{"id": "d1", "name": "pool"}]}

    with pytest.raises(RuckusOneNotFoundError):
        DpskServicesResource(mock_client).get_by_name("Pool")


def test_dpsk_services_get_by_name_multiple_matches(mock_client):
    resource = DpskServicesResource(mock_client)

    mock_client.post.return_value = {
        "data": [
            {"id": "d1", "name": "Pool", "passphraseFormat": "KEYBOARD_FRIENDLY"},
            {"id": "d2", "name": "Pool", "passphraseFormat": "KEYBOARD_FRIENDLY"},
        ]
    }

    with pytest.raises(ValueError):
        resource.get_by_name("Pool")
