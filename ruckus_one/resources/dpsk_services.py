"""DPSK services (DPSK pools) resource."""

import logging
from typing import Any, Dict, List, Optional, cast

from ruckus_one.exceptions import RuckusOneNotFoundError

logger = logging.getLogger(__name__)


class DpskServicesResource:
    """Resource for querying DPSK service profiles (\"DPSK pools\")."""

    _DEFAULT_FIELDS: List[str] = [
        "id",
        "name",
        "passphraseFormat",
        "networkCount",
    ]

    def __init__(self, client: Any) -> None:
        self.client = client

    def _extract_items(self, response: Any) -> List[Dict[str, Any]]:
        """Extract a list of DPSK pool dicts from the API response."""
        if response is None:
            return []
        if isinstance(response, list):
            return cast(List[Dict[str, Any]], response)
        if not isinstance(response, dict):
            return []

        # Observed shapes:
        # - POST /dpskServices/query: { "data": [...] }
        # - GET /dpskServices?name=...: { "content": [...], "pageable": {...} }
        items = response.get("data")
        if isinstance(items, list):
            return cast(List[Dict[str, Any]], items)

        content = response.get("content")
        if isinstance(content, list):
            return cast(List[Dict[str, Any]], content)

        return []

    def _extract_total(self, response: Any) -> Optional[int]:
        """Extract a total count hint from response (if present)."""
        if not isinstance(response, dict):
            return None

        # Observed on this endpoint: top-level `totalCount`
        total = response.get("totalCount")
        if isinstance(total, int):
            return total

        # Fallback to meta.total/totalCount if backend uses that shape
        meta = response.get("meta")
        if isinstance(meta, dict):
            for key in ("total", "totalCount", "count"):
                v = meta.get(key)
                if isinstance(v, int):
                    return v

        return None

    def list(
        self,
        page_size: int = 50,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List all DPSK service profiles.

        Uses POST /dpskServices/query with pagination.
        """
        effective_fields = fields or self._DEFAULT_FIELDS

        results: List[Dict[str, Any]] = []
        page = 1

        while True:
            body = {
                "page": page,
                "pageSize": page_size,
                "fields": effective_fields,
            }
            response = self.client.post("/dpskServices/query", json=body)

            items = self._extract_items(response)
            if not items:
                break

            results.extend(items)

            # Stop if the page is not full.
            if len(items) < page_size:
                break

            total = self._extract_total(response)
            if total is not None and len(results) >= total:
                break

            page += 1

        return results

    def get_by_name(
        self,
        name: str,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get a single DPSK service profile by exact name.

        Uses GET /dpskServices with query parameter `name` (exact match).

        Notes:
            - The backend POST /dpskServices/query endpoint can behave like a loose
              search (returning multiple results) even when matchFields is used.
            - This GET endpoint is deprecated upstream, but currently provides the
              most direct exact-name filtering behavior.
            - By default, the API response includes many fields; this method
              returns the full object. If `fields` is provided, the result is
              projected down to those keys only.
        """
        response = self.client.get("/dpskServices", params={"name": name})
        items = self._extract_items(response)

        if not items:
            raise RuckusOneNotFoundError(
                f"DPSK service profile with name '{name}' not found"
            )

        if len(items) > 1:
            raise ValueError(f"Multiple DPSK service profiles found with name '{name}'")

        profile = cast(Dict[str, Any], items[0])
        # By default, return the full object (API may return additional fields even
        # if a `fields` list is provided). If the caller explicitly supplies
        # `fields=...`, project down to those keys only.
        if fields is None:
            return profile

        return {k: profile[k] for k in fields if k in profile}
