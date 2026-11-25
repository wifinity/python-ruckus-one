"""Tests for the endpoint inventory, pinned headers and deprecation warnings."""

import json
import logging
from typing import Dict, List
from unittest.mock import patch

import httpx
import pytest

from ruckus_one import RuckusOneClient
from ruckus_one.api_versions import ENDPOINTS, Endpoint, find_endpoint, media_type


class TestFindEndpoint:
    def test_matches_concrete_path_to_template(self):
        endpoint = find_endpoint("put", "/venues/v1/aps/SN1/networkSettings")
        assert endpoint is not None
        assert endpoint.path == "/venues/{venueId}/aps/{serialNumber}/networkSettings"

    def test_literal_segment_beats_parameter(self):
        endpoint = find_endpoint("POST", "/venues/aps/query")
        assert endpoint is not None
        assert endpoint.path == "/venues/aps/query"

    def test_query_endpoint_is_distinct_from_create(self):
        query = find_endpoint("POST", "/venues/query")
        create = find_endpoint("POST", "/venues")
        assert query is not None and query.path == "/venues/query"
        assert create is not None and create.path == "/venues"

    def test_ignores_query_string_and_trailing_slash(self):
        endpoint = find_endpoint("GET", "/venues/abc/?fields=id")
        assert endpoint is not None
        assert endpoint.path == "/venues/{venueId}"

    def test_method_must_match(self):
        assert find_endpoint("PATCH", "/venues") is None

    def test_unknown_path(self):
        assert find_endpoint("GET", "/switches") is None

    def test_inventory_has_no_duplicates(self):
        keys = [(e.method, e.template) for e in ENDPOINTS]
        assert len(keys) == len(set(keys))


class TestEndpointHeaders:
    def test_pins_accept_and_content_type_with_body(self):
        endpoint = Endpoint("POST", "/venues/{venueId}/apGroups", "1.1", "1.1")
        assert endpoint.headers(has_body=True) == {
            "Accept": "application/vnd.ruckus.v1.1+json",
            "Content-Type": "application/vnd.ruckus.v1.1+json",
        }

    def test_no_content_type_without_body(self):
        endpoint = Endpoint("PUT", "/venues/{venueId}", "1", "1")
        assert endpoint.headers(has_body=False) == {"Accept": media_type("1")}

    def test_request_only_version(self):
        endpoint = Endpoint("POST", "/networkActivations/query", "1", None)
        assert endpoint.headers(has_body=True) == {"Content-Type": media_type("1")}

    def test_unversioned_endpoint_sends_nothing(self):
        assert Endpoint("GET", "/networks").headers(has_body=True) == {}


def make_client(
    responses: List[httpx.Response], pin: bool = True
) -> "tuple[RuckusOneClient, List[httpx.Request]]":
    sent: List[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return queue.pop(0) if queue else httpx.Response(200, json={})

    client = RuckusOneClient(
        region="us",
        tenant_id="tenant",
        client_id="id",
        client_secret="secret",
        enable_retry=False,
        pin_api_versions=pin,
    )
    client._client = httpx.Client(
        base_url=client.base_url, transport=httpx.MockTransport(handler)
    )
    return client, sent


@pytest.fixture(autouse=True)
def no_token_fetch():
    with patch.object(
        RuckusOneClient,
        "_get_headers",
        lambda self: {"Authorization": "Bearer token"},
    ):
        yield


class TestClientPinning:
    def test_post_with_body_sends_pinned_versions(self):
        client, sent = make_client([httpx.Response(200, json={"data": []})])
        client.post("/venues/query", json={"pageSize": 1})
        request = sent[0]
        assert request.headers["Accept"] == "application/vnd.ruckus.v1+json"
        assert request.headers["Content-Type"] == "application/vnd.ruckus.v1+json"
        assert json.loads(request.content) == {"pageSize": 1}

    def test_get_sends_accept_only(self):
        client, sent = make_client([httpx.Response(200, json={})])
        client.get("/venues/abc")
        assert sent[0].headers["Accept"] == "application/vnd.ruckus.v1+json"
        assert "Content-Type" not in sent[0].headers

    def test_unversioned_request_keeps_default_content_type(self):
        client, sent = make_client([httpx.Response(200, json={})])
        client.post("/dpskServices/query", json={"page": 1})
        assert sent[0].headers["Accept"] == media_type("2")
        assert sent[0].headers["Content-Type"] == "application/json"

    def test_unknown_endpoint_keeps_default_headers(self):
        client, sent = make_client([httpx.Response(200, json={})])
        client.get("/switches")
        assert "vnd.ruckus" not in sent[0].headers.get("Accept", "")

    def test_full_url_is_matched_by_path(self):
        client, sent = make_client([httpx.Response(200, json={})])
        client.get(f"{client.base_url}/activities/req-1")
        assert sent[0].headers["Accept"] == "application/vnd.ruckus.v1+json"

    def test_pinning_disabled(self):
        client, sent = make_client([httpx.Response(200, json={})], pin=False)
        client.post("/venues/query", json={})
        assert "vnd.ruckus" not in sent[0].headers.get("Accept", "")
        assert sent[0].headers["Content-Type"] == "application/json"


def deprecated_response(headers: Dict[str, str]) -> httpx.Response:
    return httpx.Response(200, json={}, headers=headers)


class TestDeprecationWarning:
    def test_warns_once_per_operation(self, caplog):
        headers = {"Ruckus-Deprecated": "true", "Ruckus-Current-Version": "1.1"}
        client, _ = make_client(
            [deprecated_response(headers), deprecated_response(headers)]
        )
        with caplog.at_level(logging.WARNING, logger="ruckus_one.client"):
            client.get("/venues/a")
            client.get("/venues/b")
        warnings = [r for r in caplog.records if "deprecation" in r.getMessage()]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "GET /venues/{venueId}" in message
        assert "pinned version 1" in message
        assert "current version 1.1" in message

    def test_unknown_endpoint_reports_raw_path(self, caplog):
        client, _ = make_client([deprecated_response({"Ruckus-Deprecated": "true"})])
        with caplog.at_level(logging.WARNING, logger="ruckus_one.client"):
            client.get("/switches")
        assert any(
            "GET /switches (pinned version unpinned, current version unknown"
            in r.getMessage()
            for r in caplog.records
        )

    @pytest.mark.parametrize("value", ["false", "0", ""])
    def test_false_values_do_not_warn(self, caplog, value):
        client, _ = make_client([deprecated_response({"Ruckus-Deprecated": value})])
        with caplog.at_level(logging.WARNING, logger="ruckus_one.client"):
            client.get("/venues/a")
        assert not [r for r in caplog.records if "deprecation" in r.getMessage()]

    def test_no_header_no_warning(self, caplog):
        client, _ = make_client([httpx.Response(200, json={})])
        with caplog.at_level(logging.WARNING, logger="ruckus_one.client"):
            client.get("/venues/a")
        assert not caplog.records

    def test_warns_on_error_responses_too(self, caplog):
        client, _ = make_client(
            [httpx.Response(404, json={}, headers={"Ruckus-Deprecated": "true"})]
        )
        with caplog.at_level(logging.WARNING, logger="ruckus_one.client"):
            with pytest.raises(Exception):
                client.get("/venues/a")
        assert any("deprecation" in r.getMessage() for r in caplog.records)


MIGRATED_CALLS = {
    "wifi_networks.all": lambda c: c.wifi_networks.all(),
    "wifi_networks.get(id)": lambda c: c.wifi_networks.get(id="n1"),
    "wifi_networks.get(name)": lambda c: c.wifi_networks.get(name="Guest"),
    "wifi_networks.filter": lambda c: c.wifi_networks.filter(filters={}),
    "wifi_networks.create": lambda c: c.wifi_networks.create(
        name="Guest", type="psk", ssid="Guest"
    ),
    "wifi_networks.update": lambda c: c.wifi_networks.update("n1", {"name": "n"}),
    "wifi_networks.delete": lambda c: c.wifi_networks.delete("n1"),
    "wifi_networks.activate_at_venue": lambda c: c.wifi_networks.activate_at_venue(
        "v1", "n1"
    ),
    "wifi_networks.deactivate_at_venue": lambda c: (
        c.wifi_networks.deactivate_at_venue("v1", "n1")
    ),
    "aps.get_by_serial": lambda c: c.aps.get_by_serial("v1", "SN1"),
    "aps.list": lambda c: c.aps.list("v1"),
    "aps.create": lambda c: c.aps.create("v1", serialNumber="SN1", name="AP"),
    "aps.delete": lambda c: c.aps.delete("v1", ["SN1"]),
    "aps.update (move)": lambda c: c.aps.update("v2", "SN1", {"name": "AP"}),
    "ap_groups.list": lambda c: c.ap_groups.list("v1"),
    "venues.filter": lambda c: c.venues.filter(filters={}),
    "venues.delete": lambda c: c.venues.delete(["v1"]),
    "dpsk_services.get_by_name": lambda c: c.dpsk_services.get_by_name("Pool"),
}

CANNED = {
    "/venues/aps/query": {"data": [{"serialNumber": "SN1", "venueId": "v1"}]},
    "/wifiNetworks/query": {"data": [{"id": "n1", "name": "Guest"}]},
    "/dpskServices/query": {"data": [{"id": "d1", "name": "Pool"}]},
    "/venues/apGroups/query": {"data": [{"id": "g", "isDefault": True}]},
    "/activities/r": {"status": "SUCCESS"},
}


@pytest.mark.parametrize("name", sorted(MIGRATED_CALLS))
def test_migrated_methods_only_call_inventoried_endpoints(name):
    """Every request a migrated method sends matches an ENDPOINTS entry and is pinned."""
    sent: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(
            200, json=CANNED.get(request.url.path, {"id": "x", "requestId": "r"})
        )

    client, _ = make_client([])
    client._client = httpx.Client(
        base_url=client.base_url, transport=httpx.MockTransport(handler)
    )

    MIGRATED_CALLS[name](client)

    assert sent
    for request in sent:
        endpoint = find_endpoint(request.method, request.url.path)
        assert endpoint is not None, f"{request.method} {request.url.path}"
        if endpoint.response_version:
            assert request.headers["Accept"] == media_type(endpoint.response_version)
