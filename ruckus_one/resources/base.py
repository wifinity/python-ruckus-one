"""Base resource class for API resources."""

import logging
from typing import Any, Dict, List, Optional, Union, cast

from ruckus_one.exceptions import RuckusOneNotFoundError

logger = logging.getLogger(__name__)


class BaseResource:
    """Base class for API resources providing common CRUD operations."""

    # Class attributes for required fields (can be overridden by subclasses)
    _required_fields_create: List[str] = []
    _required_fields_update: List[str] = []

    def __init__(self, client: Any, path: str) -> None:
        """Initialize the resource.

        Args:
            client: RuckusOneClient instance
            path: Base API path for this resource (e.g., "/api/tenant/{tenantId}/venues")
        """
        self.client = client
        self.path = path.rstrip("/")
        # Cache for name-based lookups
        self._name_cache: Dict[str, str] = {}
        logger.debug(f"Initialized {self.__class__.__name__} with path {self.path}")

    def all(self) -> List[Dict[str, Any]]:
        """Get all items, automatically handling pagination.

        Handles both dict responses (with "data" and "meta" keys) and
        bare list responses (as returned by some Ruckus One endpoints).

        Returns:
            List of all items across all pages
        """
        all_items: List[Dict[str, Any]] = []
        offset = 0
        limit = 100  # Default page size

        while True:
            params = {"limit": limit, "offset": offset}
            response = self.client.get(self.path, params=params)

            if not response:
                break

            # Handle both dict-with-data and bare list responses
            if isinstance(response, list):
                items = response
                meta: Dict[str, Any] = {}
            else:
                items = response.get("data", [])
                meta = response.get("meta", {}) or {}

            if not items:
                break

            all_items.extend(items)

            # Check if we've fetched all items
            # If no meta/total info, stop when we get fewer items than requested
            total = meta.get("total")

            if total is not None:
                # We have total count, check if we've fetched all
                if len(all_items) >= total:
                    break
            elif len(items) < limit:
                # No more items available
                break

            offset += limit

        logger.debug(f"Fetched {len(all_items)} items from {self.path}")
        return all_items

    def get(
        self, id: Optional[Union[int, str]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Get a single item by ID or by filter parameters.

        Args:
            id: Item ID (optional if using filter parameters)
            **kwargs: Filter parameters to search by (e.g., name="Venue Name")

        Returns:
            Item data

        Raises:
            RuckusOneNotFoundError: If item not found
            ValueError: If multiple items found or invalid parameters
        """
        # If ID is provided, use direct lookup
        if id is not None:
            response = self.client.get(f"{self.path}/{id}")
            if not response:
                raise RuckusOneNotFoundError(f"Item with id {id} not found")
            return cast(Dict[str, Any], response)

        # If filter parameters are provided, fetch all items and filter client-side
        # (API only supports get-by-ID, not filtering by other parameters)
        if kwargs:
            # Fetch all items
            all_items = self.all()

            # Apply client-side filtering
            items = self._filter_items_client_side(all_items, **kwargs)

            if len(items) == 0:
                raise RuckusOneNotFoundError("No items found matching the criteria")
            if len(items) > 1:
                raise ValueError(
                    f"Multiple items found ({len(items)}). "
                    "Use filter() to get all results or be more specific."
                )

            return cast(Dict[str, Any], items[0])

        # Neither ID nor filter parameters provided
        raise ValueError("Either 'id' or filter parameters must be provided")

    def filter(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """Get filtered list of items.

        Handles both dict responses (with "data" key) and bare list responses.

        Args:
            **kwargs: Filter parameters to pass as query parameters or POST body

        Returns:
            List of filtered items
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

    def _validate_required(
        self,
        data: Dict[str, Any],
        required_fields: List[str],
        operation: str = "create",
    ) -> None:
        """Validate that all required fields are present in data.

        Args:
            data: Dictionary of provided parameters
            required_fields: List of required field names
            operation: Operation name for error message (e.g., "create", "update")

        Raises:
            ValueError: If any required fields are missing
        """
        missing = []
        for field in required_fields:
            value = data.get(field)
            if value is None:
                missing.append(field)
            elif isinstance(value, str) and not value.strip():
                missing.append(field)
            elif isinstance(value, dict) and not value:
                # Empty dict - let API validate and provide helpful error message
                # Don't treat as missing, allow it to pass through
                pass
            elif isinstance(value, list) and not value:
                # Empty list is considered missing
                missing.append(field)

        if missing:
            raise ValueError(
                f"Missing required fields for {operation}: {', '.join(missing)}"
            )

    def create(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a new item.

        Args:
            **kwargs: Item data to create

        Returns:
            Created item data (may include requestId for async operations)

        Raises:
            ValueError: If required fields are missing
        """
        required = getattr(self, "_required_fields_create", [])
        if required:
            self._validate_required(kwargs, required, "create")
        response = self.client.post(self.path, json=kwargs)
        if not response:
            raise ValueError("Failed to create item")
        return cast(Dict[str, Any], response)

    def update(self, id: Union[int, str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing item.

        Args:
            id: Item ID
            data: Data to update

        Returns:
            Updated item data (may include requestId for async operations)

        Raises:
            ValueError: If required fields are missing
        """
        required = getattr(self, "_required_fields_update", [])
        if required:
            self._validate_required(data, required, "update")
        response = self.client.put(f"{self.path}/{id}", json=data)
        if not response:
            raise ValueError(f"Failed to update item with id {id}")
        return cast(Dict[str, Any], response)

    def delete(self, id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Delete an item.

        Args:
            id: Item ID

        Returns:
            Response data or None
        """
        result = self.client.delete(f"{self.path}/{id}")
        return cast(Optional[Dict[str, Any]], result)

    def get_by_name(self, name: str, use_cache: bool = True) -> Dict[str, Any]:
        """Get an item by name, with optional caching.

        Args:
            name: Item name to search for
            use_cache: Whether to use cached name → ID mapping

        Returns:
            Item data

        Raises:
            RuckusOneNotFoundError: If item not found
            ValueError: If multiple items found
        """
        # Check cache first
        if use_cache and name in self._name_cache:
            cached_id = self._name_cache[name]
            logger.debug(f"Using cached ID {cached_id} for name '{name}'")
            return self.get(id=cached_id)

        # Fetch from API
        try:
            item = self.get(name=name)
            # Cache the name → ID mapping
            if use_cache and "id" in item:
                self._name_cache[name] = str(item["id"])
                logger.debug(f"Cached name '{name}' → ID {item['id']}")
            return item
        except RuckusOneNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error fetching item by name '{name}': {e}")
            raise

    def clear_name_cache(self) -> None:
        """Clear the name-based lookup cache."""
        logger.debug(f"Clearing name cache for {self.__class__.__name__}")
        self._name_cache.clear()

    def _filter_items_client_side(
        self, items: List[Dict[str, Any]], **filters: Any
    ) -> List[Dict[str, Any]]:
        """Filter items client-side based on provided criteria.

        Args:
            items: List of items to filter
            **filters: Filter criteria (field=value pairs)

        Returns:
            Filtered list of items matching all criteria
        """
        if not filters:
            return items

        filtered = []
        for item in items:
            match = True
            for key, value in filters.items():
                item_value = item.get(key)
                # Handle case-insensitive string comparison
                if isinstance(value, str) and isinstance(item_value, str):
                    if item_value.lower() != value.lower():
                        match = False
                        break
                elif item_value != value:
                    match = False
                    break
            if match:
                filtered.append(item)

        return filtered
