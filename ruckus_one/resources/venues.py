"""Venues resource."""

import logging
import re
from typing import Any, Dict, List, Optional, Union, cast

import pycountry

from ruckus_one.exceptions import RuckusOneNotFoundError
from ruckus_one.resources.base import BaseResource

logger = logging.getLogger(__name__)


class VenuesResource(BaseResource):
    """Resource for managing venues."""

    _required_fields_create = ["name", "address"]
    _QUERY_PAGE_SIZE = 100

    def __init__(self, client: Any) -> None:
        """Initialize venues resource."""
        path = "/venues"
        super().__init__(client, path)

    def _query(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """POST a body to /venues/query and return the response dict."""
        response = self.client.post(f"{self.path}/query", json=body)
        return response if isinstance(response, dict) else {}

    def all(self) -> List[Dict[str, Any]]:
        """Get all venues by paging through POST /venues/query.

        The venue collection accepts POST only: GET /venues returns 405.

        Returns:
            List of all venues across all pages
        """
        venues: List[Dict[str, Any]] = []
        page = 1

        while True:
            response = self._query({"page": page, "pageSize": self._QUERY_PAGE_SIZE})
            items = response.get("data") or []
            venues.extend(items)

            total = response.get("totalCount")
            if len(items) < self._QUERY_PAGE_SIZE:
                break
            if isinstance(total, int) and len(venues) >= total:
                break
            page += 1

        logger.debug(f"Fetched {len(venues)} venues from {self.path}/query")
        return venues

    def get(
        self, id: Optional[Union[int, str]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Get a single venue by ID or by filter parameters.

        A lookup by `name` alone resolves the ID with an exact-match
        `filters.name` query, then fetches the full venue by ID, so the result
        has the same shape as a lookup by ID. Any other filter falls back to
        client-side filtering over `all()`.

        Args:
            id: Venue ID (optional if using filter parameters)
            **kwargs: Filter parameters to search by (e.g., name="Venue Name")

        Returns:
            Venue data

        Raises:
            RuckusOneNotFoundError: If no venue matches
            ValueError: If multiple venues match or parameters are invalid
        """
        if id is not None or set(kwargs) != {"name"}:
            return super().get(id, **kwargs)

        name = kwargs["name"]
        response = self._query(
            {
                "page": 1,
                "pageSize": self._QUERY_PAGE_SIZE,
                "fields": ["id", "name"],
                "filters": {"name": [name]},
            }
        )
        matches = response.get("data") or []

        if not matches:
            raise RuckusOneNotFoundError(f"Venue with name '{name}' not found")
        if len(matches) > 1:
            raise ValueError(f"Multiple venues found with name '{name}'")

        venue_id = matches[0].get("id")
        if not venue_id:
            raise ValueError(f"Venue query result for '{name}' has no id")

        return super().get(id=venue_id)

    def get_by_name(self, name: str, use_cache: bool = True) -> Dict[str, Any]:
        """Get venue by name, with optional caching.

        Args:
            name: Venue name to search for
            use_cache: Whether to use cached name → ID mapping

        Returns:
            Venue data

        Raises:
            RuckusOneNotFoundError: If venue not found
            ValueError: If multiple venues found
        """
        return super().get_by_name(name, use_cache=use_cache)

    def filter(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """Get filtered list of venues.

        Posts ``kwargs`` as the body of POST /venues/query (``filters``,
        ``fields``, ``searchString``, ``page``, ``pageSize``, ...) and returns
        one page of query rows.

        Args:
            **kwargs: Query body

        Returns:
            List of filtered venues
        """
        response = self.client.post(f"{self.path}/query", json=kwargs)
        if not response:
            return []

        # Handle both dict-with-data and bare list responses
        if isinstance(response, list):
            return cast(List[Dict[str, Any]], response)

        data = response.get("data", [])
        return cast(List[Dict[str, Any]], data)

    def _validate_address_country(self, country: str) -> None:
        """Validate country name using pycountry.

        Only accepts full country names, not ISO codes.

        Args:
            country: Country name to validate

        Raises:
            ValueError: If country is invalid, with suggestion if available
        """
        if not isinstance(country, str) or not country.strip():
            return  # Skip validation if not a string or empty

        country_clean = country.strip()

        # Reject ISO codes (2-3 letters, case-insensitive)
        if re.match(r"^[A-Za-z]{2,3}$", country_clean):
            # Check if it's actually an ISO code by trying to lookup
            try:
                country_obj = pycountry.countries.lookup(country_clean)
                # If lookup succeeds and the input matches an ISO code, reject it
                if (
                    country_obj.alpha_2.upper() == country_clean.upper()
                    or country_obj.alpha_3.upper() == country_clean.upper()
                ):
                    raise ValueError(
                        f"Country code '{country}' is not accepted. "
                        "Please use the full country name (e.g., 'United Kingdom' instead of 'GB')."
                    )
            except LookupError:
                # Not an ISO code, continue with name validation
                pass

        # Try exact match by name (case-insensitive)
        try:
            country_obj = pycountry.countries.lookup(country_clean)
            # Verify it was matched by name, not ISO code
            # Check if the input (case-insensitive) matches the country's name
            if country_obj.name.lower() == country_clean.lower():
                return  # Valid country name
            # If lookup found by ISO code, it means the name doesn't match
            # Reject it
        except LookupError:
            pass

        # No valid match found
        raise ValueError(
            f"Invalid country name '{country}'. "
            "Please use a valid full country name (e.g., 'United Kingdom', 'United States')."
        )

    def create(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a new venue.

        Validates basic address structure and country name. Detailed validation is handled by the API.

        Args:
            **kwargs: Venue data to create

        Returns:
            Created venue data (may include requestId for async operations)

        Raises:
            ValueError: If address is provided but not a dictionary, or if country name is invalid
        """
        # Minimal pre-validation: ensure address is a dict if provided
        # Allow empty dicts to pass through so API can provide helpful error messages
        if "address" in kwargs:
            address = kwargs["address"]
            if address is not None and not isinstance(address, dict):
                raise ValueError(
                    f"address must be a dictionary, got {type(address).__name__}"
                )

            # Validate country name if present
            if isinstance(address, dict) and "country" in address:
                self._validate_address_country(address["country"])

        return super().create(**kwargs)

    def update(self, id: Union[int, str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing venue.

        Args:
            id: Venue ID
            data: Data to update

        Returns:
            Updated venue data (may include requestId for async operations)
        """
        return super().update(id, data)

    def delete(
        self, id: Union[int, str, List[Union[int, str]]]
    ) -> Optional[Dict[str, Any]]:
        """Delete one or more venues.

        Each venue is deleted with DELETE /venues/{venueId}.

        Args:
            id: Single venue ID or list of venue IDs

        Returns:
            The delete response (``requestId``) for a single ID, or
            ``{"responses": [...]}`` with one response per venue for a list.
        """
        if isinstance(id, (int, str)):
            return cast(
                Optional[Dict[str, Any]], self.client.delete(f"{self.path}/{id}")
            )
        if not isinstance(id, list):
            raise ValueError(
                f"id must be int, str, or list of int/str, got {type(id).__name__}"
            )
        return {
            "responses": [
                self.client.delete(f"{self.path}/{venue_id}") for venue_id in id
            ]
        }
