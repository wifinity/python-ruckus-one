"""RADIUS server profiles resource."""

import logging
from typing import Any, Dict, List, Optional, cast

from ruckus_one.exceptions import RuckusOneNotFoundError

logger = logging.getLogger(__name__)


class RadiusServerProfilesResource:
    """Resource for querying RADIUS server profiles.

    API endpoint:
      - POST /radiusServerProfiles/query
    """

    _DEFAULT_FIELDS: List[str] = ["id", "name", "primary", "type"]

    def __init__(self, client: Any) -> None:
        self.client = client

    def _extract_items(self, response: Any) -> List[Dict[str, Any]]:
        """Extract a list of profile dicts from the API response."""
        if response is None:
            return []
        if isinstance(response, list):
            return cast(List[Dict[str, Any]], response)
        if not isinstance(response, dict):
            return []

        # Common shapes in this codebase:
        # - { "data": [...] }
        # - sometimes endpoints return a bare list
        for key in ("data", "radiusServerProfiles", "profiles", "items"):
            value = response.get(key)
            if isinstance(value, list):
                return cast(List[Dict[str, Any]], value)

        return []

    def _extract_total(self, response: Any) -> Optional[int]:
        """Extract a total count hint from response meta (if present)."""
        if not isinstance(response, dict):
            return None
        meta = response.get("meta")
        if not isinstance(meta, dict):
            return None

        for key in ("total", "totalCount", "count"):
            value = meta.get(key)
            if isinstance(value, int):
                return value
        return None

    def list(
        self,
        page_size: int = 50,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List all radius server profiles.

        Uses POST /radiusServerProfiles/query with pagination.
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
            response = self.client.post("/radiusServerProfiles/query", json=body)

            items = self._extract_items(response)
            if not items:
                break

            results.extend(items)

            # Stop if the page is not full.
            if len(items) < page_size:
                break

            # Stop if we have total count metadata and reached it.
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
        """Get a single radius server profile by exact name.

        Uses POST /radiusServerProfiles/query with `matchFields` on `name`.
        """
        effective_fields = fields or self._DEFAULT_FIELDS

        body = {
            "page": 1,
            "pageSize": 50,
            "fields": effective_fields,
            "matchFields": [{"field": "name", "value": name}],
        }
        response = self.client.post("/radiusServerProfiles/query", json=body)

        items = self._extract_items(response)
        if not items:
            raise RuckusOneNotFoundError(
                f"Radius server profile with name '{name}' not found"
            )

        if len(items) > 1:
            raise ValueError(
                f"Multiple radius server profiles found with name '{name}'"
            )

        return cast(Dict[str, Any], items[0])
