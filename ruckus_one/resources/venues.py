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

    def __init__(self, client: Any) -> None:
        """Initialize venues resource."""
        path = "/venues"
        super().__init__(client, path)

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

        Supports POST /venues/query for filtering.

        Args:
            **kwargs: Filter parameters

        Returns:
            List of filtered venues
        """
        # Try POST /query endpoint first (Ruckus One pattern)
        query_path = f"{self.path}/query"
        try:
            response = self.client.post(query_path, json=kwargs)
        except RuckusOneNotFoundError:
            # Fall back to GET with params
            response = self.client.get(self.path, params=kwargs)

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

        Per Postman collection, delete uses DELETE /venues with JSON array body.

        Args:
            id: Single venue ID or list of venue IDs

        Returns:
            Response data (may include requestId for async operations)
        """
        # Normalize to list
        if isinstance(id, (int, str)):
            venue_ids = [id]
        elif isinstance(id, list):
            venue_ids = id
        else:
            raise ValueError(
                f"id must be int, str, or list of int/str, got {type(id).__name__}"
            )

        # Convert all IDs to strings (Postman shows string IDs)
        venue_ids_str = [str(venue_id) for venue_id in venue_ids]

        # DELETE /venues with JSON array body per Postman
        response = self.client.delete(self.path, json=venue_ids_str)
        return cast(Optional[Dict[str, Any]], response)
