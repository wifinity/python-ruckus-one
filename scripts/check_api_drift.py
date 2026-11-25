#!/usr/bin/env python3
"""Compare the SDK's endpoint inventory with the published Ruckus One API specs.

Downloads every OpenAPI spec listed on docs.ruckus.cloud (current and
deprecated sections) and reports, for each endpoint in
``ruckus_one.api_versions.ENDPOINTS``:

- removed: the operation is in no published spec
- deprecated: the operation is in the deprecated section or flagged deprecated
- newer version: the spec offers a request/response version above the pin

The report also lists the newest batch of the published API change history
and the entries on the Upcoming Changes page.

Output is markdown, or JSON with ``--json``. Exit codes: 0 no findings (and
always 0 with ``--json`` once the check ran), 2 findings reported, 1 the check
itself failed.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx

from ruckus_one.api_versions import ENDPOINTS, Endpoint, normalise_template

DOCS_URL = "https://docs.ruckus.cloud"
SECTIONS = ("api", "deprecated_apis")
SIDEBAR_URL = DOCS_URL + "/page-data/shared/sidebar-{section}/sidebars.yaml.json"
SPEC_URL = DOCS_URL + "/_spec/{section}/{slug}.json"
UPCOMING_PATH = "/api/docs/upcoming-changes"
UPCOMING_DATA_URL = DOCS_URL + "/page-data" + UPCOMING_PATH + "/data.json"
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
VERSION_RE = re.compile(r"application/vnd\.ruckus\.v([\d.]+)\+json")


@dataclass(frozen=True)
class Operation:
    """An operation as published in the specs."""

    path: str
    spec: str
    deprecated: bool
    request_version: Optional[str]
    response_version: Optional[str]


@dataclass(frozen=True)
class Finding:
    kind: str
    endpoint: Endpoint
    detail: str

    @property
    def key(self) -> str:
        """Stable identity of the finding, for tracking it across runs."""
        return f"{self.kind}|{self.endpoint.method}|{self.endpoint.path}|{self.detail}"

    def as_dict(self) -> Dict[str, str]:
        return {
            "key": self.key,
            "kind": self.kind,
            "method": self.endpoint.method,
            "path": self.endpoint.path,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Report:
    findings: List[Finding]
    batches: List[Tuple[str, List[str]]]
    upcoming: List[Dict[str, str]]

    def as_dict(self) -> Dict[str, Any]:
        date, links = self.batches[0] if self.batches else (None, [])
        return {
            "findings": [f.as_dict() for f in sort_findings(self.findings)],
            "change_history": {"latest": date, "links": links},
            "upcoming_changes": self.upcoming,
        }


def version_key(version: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def latest_version(content_types: Iterable[str]) -> Optional[str]:
    versions = [
        m.group(1) for ct in content_types for m in [VERSION_RE.search(ct)] if m
    ]
    return max(versions, key=version_key) if versions else None


def spec_slugs(sidebar: Dict[str, Any], section: str) -> List[str]:
    """Spec slugs linked from a docs sidebar, e.g. ``wifi-21.3.5.47``."""
    text = json.dumps(sidebar, separators=(",", ":"))
    links = re.findall(r'"link":"/%s/([^/"#]+)' % re.escape(section), text)
    return sorted({slug for slug in links if re.search(r"-\d[\d._]*$", slug)})


def change_history_batches(sidebar: Dict[str, Any]) -> List[Tuple[str, List[str]]]:
    """Dated change-history batches, newest first, with their page links."""

    def walk(items: Sequence[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        for item in items:
            if item.get("label") == "Change History":
                return list(item.get("items", []))
            found = walk(item.get("items", []))
            if found is not None:
                return found
        return None

    def links(items: Sequence[Dict[str, Any]]) -> List[str]:
        out: List[str] = []
        for item in items:
            if item.get("link"):
                out.append(DOCS_URL + item["link"])
            out.extend(links(item.get("items", [])))
        return out

    groups = walk(sidebar.get("items", [])) or []
    batches = [
        (group["label"], links(group.get("items", [])))
        for group in groups
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(group.get("label", "")))
    ]
    return sorted(batches, key=lambda batch: batch[0], reverse=True)


def index_operations(
    specs: Iterable[Tuple[str, bool, Dict[str, Any]]],
) -> Dict[Tuple[str, str], Operation]:
    """Index operations by (method, template). Current entries win over deprecated."""
    index: Dict[Tuple[str, str], Operation] = {}
    for name, deprecated_section, spec in specs:
        for path, operations in (spec.get("paths") or {}).items():
            for method, op in operations.items():
                if method.upper() not in HTTP_METHODS or not isinstance(op, dict):
                    continue
                request_types = (
                    (op.get("requestBody") or {}).get("content") or {}
                ).keys()
                response_types = [
                    content_type
                    for status, response in (op.get("responses") or {}).items()
                    if str(status).startswith("2") and isinstance(response, dict)
                    for content_type in (response.get("content") or {})
                ]
                operation = Operation(
                    path=path,
                    spec=name,
                    deprecated=deprecated_section or bool(op.get("deprecated")),
                    request_version=latest_version(request_types),
                    response_version=latest_version(response_types),
                )
                key = (method.upper(), normalise_template(path))
                existing = index.get(key)
                if existing is None or (
                    existing.deprecated and not operation.deprecated
                ):
                    index[key] = operation
    return index


def is_newer(published: Optional[str], pinned: Optional[str]) -> bool:
    if published is None:
        return False
    return pinned is None or version_key(published) > version_key(pinned)


def compare(
    endpoints: Iterable[Endpoint], index: Dict[Tuple[str, str], Operation]
) -> List[Finding]:
    findings: List[Finding] = []
    for endpoint in endpoints:
        operation = index.get((endpoint.method, endpoint.template))
        if operation is None:
            findings.append(Finding("removed", endpoint, "not in any published spec"))
            continue
        if operation.deprecated:
            findings.append(Finding("deprecated", endpoint, f"in {operation.spec}"))
        for direction, published, pinned in (
            ("request", operation.request_version, endpoint.request_version),
            ("response", operation.response_version, endpoint.response_version),
        ):
            if is_newer(published, pinned):
                findings.append(
                    Finding(
                        "newer version",
                        endpoint,
                        f"{direction} v{published} published, pinned "
                        f"{'v' + pinned if pinned else 'none'}",
                    )
                )
    return findings


def upcoming_changes(page_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Entries on the Upcoming Changes page: one per level-3 heading."""
    entries: List[Dict[str, str]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            attributes = node.get("attributes") or {}
            if node.get("name") == "Heading" and attributes.get("level") == 3:
                title = "".join(
                    c for c in node.get("children", []) if isinstance(c, str)
                )
                entries.append(
                    {
                        "id": attributes.get("id", ""),
                        "title": title.strip(),
                        "url": f"{DOCS_URL}{UPCOMING_PATH}#{attributes.get('id', '')}",
                    }
                )
            for child in node.get("children", []):
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(((page_data.get("props") or {}).get("ast")) or {})
    return entries


def sort_findings(findings: Iterable[Finding]) -> List[Finding]:
    order = {"removed": 0, "deprecated": 1, "newer version": 2}
    return sorted(
        findings, key=lambda f: (order[f.kind], f.endpoint.path, f.endpoint.method)
    )


def render(report: Report) -> str:
    out = ["# Ruckus One API drift report", ""]
    if report.findings:
        out += [
            f"{len(report.findings)} finding(s) against the SDK endpoint inventory "
            "(`ruckus_one/api_versions.py`).",
            "",
            "| Kind | Method | Path | Detail |",
            "|------|--------|------|--------|",
        ]
        for f in sort_findings(report.findings):
            out.append(
                f"| {f.kind} | {f.endpoint.method} | `{f.endpoint.path}` | {f.detail} |"
            )
    else:
        out.append("No drift: every SDK endpoint is published, current and pinned.")
    out += [
        "",
        "Deprecated operations are removed in the annual March window, at least six "
        f"months after deprecation. Policy: {DOCS_URL}/api/docs/versioning",
        "",
        "## Upcoming changes",
        "",
    ]
    out += [f"- [{e['title']}]({e['url']})" for e in report.upcoming] or ["- none"]
    if report.batches:
        date, links = report.batches[0]
        out += ["", f"## Latest API change history batch: {date}", ""]
        out += [f"- {link}" for link in links]
    out.append("")
    return "\n".join(out)


def fetch_specs(
    client: httpx.Client,
) -> Tuple[List[Tuple[str, bool, Dict[str, Any]]], Dict[str, Any]]:
    specs: List[Tuple[str, bool, Dict[str, Any]]] = []
    api_sidebar: Dict[str, Any] = {}
    for section in SECTIONS:
        response = client.get(SIDEBAR_URL.format(section=section))
        response.raise_for_status()
        sidebar = response.json()
        if section == "api":
            api_sidebar = sidebar
        slugs = spec_slugs(sidebar, section)
        if not slugs:
            raise RuntimeError(f"no specs listed in the {section} sidebar")
        for slug in slugs:
            spec = client.get(SPEC_URL.format(section=section, slug=slug))
            spec.raise_for_status()
            specs.append((f"{section}/{slug}", section != "api", spec.json()))
    return specs, api_sidebar


def fetch_upcoming(client: httpx.Client) -> List[Dict[str, str]]:
    response = client.get(UPCOMING_DATA_URL)
    response.raise_for_status()
    return upcoming_changes(response.json())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--report", help="also write the markdown report to this file")
    parser.add_argument("--json", action="store_true", help="print JSON, exit 0")
    args = parser.parse_args(argv)

    try:
        with httpx.Client(
            timeout=120,
            follow_redirects=True,
            headers={"User-Agent": "api-drift-check"},
        ) as client:
            specs, sidebar = fetch_specs(client)
            upcoming = fetch_upcoming(client)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        print(f"API drift check failed: {exc}", file=sys.stderr)
        return 1

    report = Report(
        findings=compare(ENDPOINTS, index_operations(specs)),
        batches=change_history_batches(sidebar),
        upcoming=upcoming,
    )
    markdown = render(report)
    if args.report:
        with open(args.report, "w") as handle:
            handle.write(markdown)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
        return 0
    print(markdown)
    return 2 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
