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
    _SEARCH_PAGE_SIZE = 100

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

        items = response.get("data")
        if isinstance(items, list):
            return cast(List[Dict[str, Any]], items)
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

    def _query_all(self, body: Dict[str, Any], page_size: int) -> List[Dict[str, Any]]:
        """Page through POST /dpskServices/query with ``body``."""
        results: List[Dict[str, Any]] = []
        page = 1

        while True:
            response = self.client.post(
                "/dpskServices/query",
                json={**body, "page": page, "pageSize": page_size},
            )

            items = self._extract_items(response)
            if not items:
                break

            results.extend(items)

            if len(items) < page_size:
                break

            total = self._extract_total(response)
            if total is not None and len(results) >= total:
                break

            page += 1

        return results

    def list(
        self,
        page_size: int = 50,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List all DPSK service profiles.

        Uses POST /dpskServices/query with pagination.
        """
        return self._query_all({"fields": fields or self._DEFAULT_FIELDS}, page_size)

    def get_by_name(
        self,
        name: str,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get a single DPSK service profile by exact name.

        Searches POST /dpskServices/query with ``searchString`` on ``name`` and
        keeps the rows whose name equals ``name`` exactly: the search is a
        substring match, so ``"Pool"`` also returns ``"Pool 2"``.

        Query rows are full pool objects. If ``fields`` is provided, the result
        is projected down to those keys only.
        """
        rows = self._query_all(
            {"searchString": name, "searchTargetFields": ["name"]},
            self._SEARCH_PAGE_SIZE,
        )
        items = [row for row in rows if row.get("name") == name]

        if not items:
            raise RuckusOneNotFoundError(
                f"DPSK service profile with name '{name}' not found"
            )

        if len(items) > 1:
            raise ValueError(f"Multiple DPSK service profiles found with name '{name}'")

        profile = cast(Dict[str, Any], items[0])
        if fields is None:
            return profile

        return {k: profile[k] for k in fields if k in profile}
