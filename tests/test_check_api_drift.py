"""Tests for scripts/check_api_drift.py."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from ruckus_one.api_versions import Endpoint

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_api_drift.py"
spec = importlib.util.spec_from_file_location("check_api_drift", SCRIPT)
drift = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(drift)  # type: ignore[union-attr]


def operation(request=None, response=None, deprecated=False):
    op = {"responses": {"200": {"content": {ct: {} for ct in response or []}}}}
    if request:
        op["requestBody"] = {"content": {ct: {} for ct in request}}
    if deprecated:
        op["deprecated"] = True
    return op


V = "application/vnd.ruckus.v{}+json".format
JSON = "application/json"

CURRENT = {
    "paths": {
        "/venues/{id}": {
            "get": operation(response=[JSON, V("1"), V("1.1")]),
            "put": operation(request=[JSON, V("1")], response=[JSON, V("1")]),
            "parameters": [],
        },
        "/venues/query": {"post": operation(request=[JSON], response=[JSON, V("1")])},
        "/old": {"get": operation(response=[JSON], deprecated=True)},
    }
}
DEPRECATED = {"paths": {"/networks": {"get": operation(response=[JSON])}}}


@pytest.fixture
def index():
    return drift.index_operations(
        [("api/venue-1", False, CURRENT), ("deprecated_apis/wifi-1", True, DEPRECATED)]
    )


def test_latest_version_orders_numerically():
    assert drift.latest_version([JSON, V("1.2"), V("1.10"), V("1")]) == "1.10"
    assert drift.latest_version([JSON]) is None


def test_index_reads_versions_per_direction(index):
    op = index[("PUT", "/venues/{}")]
    assert (op.request_version, op.response_version, op.deprecated) == ("1", "1", False)
    assert index[("GET", "/networks")].deprecated is True
    assert index[("GET", "/old")].deprecated is True
    assert ("PARAMETERS", "/venues/{}") not in index


def test_current_entry_wins_over_deprecated_section():
    index = drift.index_operations(
        [
            ("deprecated_apis/x", True, DEPRECATED),
            ("api/x", False, {"paths": {"/networks": {"get": operation()}}}),
        ]
    )
    assert index[("GET", "/networks")].deprecated is False


def test_compare_reports_each_kind(index):
    endpoints = [
        Endpoint("GET", "/venues/{venueId}", None, "1"),
        Endpoint("PUT", "/venues/{venueId}", "1", "1"),
        Endpoint("POST", "/venues/query", None, None),
        Endpoint("GET", "/networks"),
        Endpoint("GET", "/gone"),
    ]
    found = {
        (f.kind, f.endpoint.method, f.endpoint.path, f.detail)
        for f in drift.compare(endpoints, index)
    }
    assert found == {
        (
            "newer version",
            "GET",
            "/venues/{venueId}",
            "response v1.1 published, pinned v1",
        ),
        (
            "newer version",
            "POST",
            "/venues/query",
            "response v1 published, pinned none",
        ),
        ("deprecated", "GET", "/networks", "in deprecated_apis/wifi-1"),
        ("removed", "GET", "/gone", "not in any published spec"),
    }


def test_clean_inventory_has_no_findings(index):
    assert drift.compare([Endpoint("PUT", "/venues/{venueId}", "1", "1")], index) == []


SIDEBAR = {
    "items": [
        {"type": "link", "label": "Overview", "link": "/api"},
        {"type": "link", "label": "Versioning", "link": "/api/docs/versioning"},
        {"type": "link", "label": "Wi-Fi", "link": "/api/wifi-21.3.5.47"},
        {"type": "link", "label": "Wi-Fi op", "link": "/api/wifi-21.3.5.47/ap/getap"},
        {"type": "link", "label": "Workflow", "link": "/api/workflow-api-0.0.4_1"},
        {
            "type": "group",
            "label": "Change History",
            "items": [
                {
                    "type": "group",
                    "label": "2026-10-20",
                    "items": [{"type": "link", "link": "/change_history/2026-10/a"}],
                },
                {
                    "type": "group",
                    "label": "2026-11-20",
                    "items": [
                        {
                            "type": "group",
                            "label": "Wi-Fi Services",
                            "items": [
                                {"type": "link", "link": "/change_history/2026-11/b"},
                                {"type": "link", "link": "/change_history/2026-11/c"},
                            ],
                        }
                    ],
                },
            ],
        },
    ]
}


def test_spec_slugs_keep_only_versioned_specs():
    assert drift.spec_slugs(SIDEBAR, "api") == [
        "wifi-21.3.5.47",
        "workflow-api-0.0.4_1",
    ]


def test_change_history_batches_newest_first():
    batches = drift.change_history_batches(SIDEBAR)
    assert [date for date, _ in batches] == ["2026-11-20", "2026-10-20"]
    assert batches[0][1] == [
        "https://docs.ruckus.cloud/change_history/2026-11/b",
        "https://docs.ruckus.cloud/change_history/2026-11/c",
    ]


UPCOMING_PAGE = {
    "props": {
        "ast": {
            "name": "article",
            "children": [
                {
                    "name": "Heading",
                    "attributes": {"level": 2, "id": "upcoming-changes"},
                    "children": ["Upcoming Changes"],
                },
                {
                    "name": "Heading",
                    "attributes": {"level": 3, "id": "msp-licensing"},
                    "children": ["MSP Licensing APIs"],
                },
                {"name": "p", "children": ["Body text"]},
                {
                    "name": "Heading",
                    "attributes": {"level": 3, "id": "wifi-networks"},
                    "children": ["Wi-Fi ", "Networks"],
                },
            ],
        }
    }
}


def test_upcoming_changes_lists_level_three_headings():
    assert drift.upcoming_changes(UPCOMING_PAGE) == [
        {
            "id": "msp-licensing",
            "title": "MSP Licensing APIs",
            "url": "https://docs.ruckus.cloud/api/docs/upcoming-changes#msp-licensing",
        },
        {
            "id": "wifi-networks",
            "title": "Wi-Fi Networks",
            "url": "https://docs.ruckus.cloud/api/docs/upcoming-changes#wifi-networks",
        },
    ]


def test_upcoming_changes_handles_empty_page():
    assert drift.upcoming_changes({}) == []


def test_render_includes_findings_upcoming_and_batch(index):
    report = drift.Report(
        findings=drift.compare([Endpoint("GET", "/gone")], index),
        batches=drift.change_history_batches(SIDEBAR),
        upcoming=drift.upcoming_changes(UPCOMING_PAGE),
    )
    markdown = drift.render(report)
    assert "| removed | GET | `/gone` |" in markdown
    assert "- [MSP Licensing APIs](" in markdown
    assert "Latest API change history batch: 2026-11-20" in markdown


def test_render_without_findings():
    markdown = drift.render(drift.Report([], [], []))
    assert "No drift" in markdown
    assert "- none" in markdown


def test_report_as_dict_orders_findings_and_keys_are_stable(index):
    endpoints = [Endpoint("GET", "/networks"), Endpoint("GET", "/gone")]
    report = drift.Report(
        drift.compare(endpoints, index), drift.change_history_batches(SIDEBAR), []
    )
    data = report.as_dict()
    assert [f["kind"] for f in data["findings"]] == ["removed", "deprecated"]
    assert data["findings"][0]["key"] == "removed|GET|/gone|not in any published spec"
    assert data["change_history"]["latest"] == "2026-11-20"
    assert drift.Report([], [], []).as_dict()["change_history"] == {
        "latest": None,
        "links": [],
    }


def make_transport(specs):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "sidebar-api" in url:
            return httpx.Response(200, json={"items": [{"link": "/api/venue-1.0"}]})
        if "sidebar-deprecated_apis" in url:
            return httpx.Response(
                200, json={"items": [{"link": "/deprecated_apis/wifi-1.0"}]}
            )
        if "upcoming-changes" in url:
            return httpx.Response(200, json=UPCOMING_PAGE)
        for name, body in specs.items():
            if url.endswith(f"/{name}.json"):
                return httpx.Response(200, json=body)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def docs_site(monkeypatch):
    def install(specs):
        transport = make_transport(specs)
        real_client = httpx.Client
        monkeypatch.setattr(
            drift.httpx, "Client", lambda **kw: real_client(transport=transport, **kw)
        )

    return install


def test_main_exit_codes(docs_site, monkeypatch, tmp_path):
    docs_site({"venue-1.0": CURRENT, "wifi-1.0": DEPRECATED})
    monkeypatch.setattr(drift, "ENDPOINTS", (Endpoint("PUT", "/venues/{v}", "1", "1"),))
    report = tmp_path / "report.md"
    assert drift.main(["--report", str(report)]) == 0
    assert "No drift" in report.read_text()

    monkeypatch.setattr(drift, "ENDPOINTS", (Endpoint("GET", "/networks"),))
    assert drift.main([]) == 2


def test_main_json_exits_zero_with_findings(docs_site, monkeypatch, capsys):
    docs_site({"venue-1.0": CURRENT, "wifi-1.0": DEPRECATED})
    monkeypatch.setattr(drift, "ENDPOINTS", (Endpoint("GET", "/networks"),))
    assert drift.main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["findings"][0]["kind"] == "deprecated"
    assert data["upcoming_changes"][0]["id"] == "msp-licensing"


def test_main_fails_when_specs_unavailable(docs_site):
    docs_site({})
    assert drift.main([]) == 1
    assert drift.main(["--json"]) == 1
