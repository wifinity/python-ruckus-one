# Python-Ruckus-One Repository Memory

## 1) Purpose and Overview
`python-ruckus-one` is a Python client library for the Ruckus One API (venues, APs, Wi-Fi networks, AP groups, radius server profiles, DPSK services, and async “activities”/request polling).

Primary problems solved:
- Provide a typed, resource-oriented wrapper around raw REST endpoints (higher-level methods like `client.venues.get_by_name(...)`, `client.wifi_networks.activate_at_venue(...)`).
- Handle OAuth2 client-credentials authentication with in-memory token caching + refresh.
- Centralize request/response logging with sensitive header masking.
- Normalize/translate API error responses into a clear exception hierarchy.
- Provide shared “resource” behaviors: pagination, CRUD, name→ID caching, and basic client-side filtering.

The project is “client library first”: the canonical entry is `RuckusOneClient` and then resource access via attributes.

## 2) Architecture

### Runtime shape
- `RuckusOneClient` owns:
  - OAuth token manager (`OAuth2TokenManager`)
  - `httpx.Client` session (base_url + timeout)
  - Resource objects (`venues`, `radius_server_profiles`, `aps`, `wifi_networks`, `ap_groups`, `dpsk_services`, `activities`)
- Resource objects call back into the `RuckusOneClient` via `client.get/post/put/patch/delete(...)`.
- Async operations:
  - create/update/activate calls may return a `requestId`
  - `ActivitiesResource.wait_for_completion(request_id, ...)` polls `/activities/{requestId}` until `SUCCESS` or failure/timeout.

### Logical layers
- Transport/API layer: `ruckus_one/client.py`
  - URL normalization, retry policy, error parsing, exception raising.
- Auth layer: `ruckus_one/auth.py`
  - OAuth2 client-credentials token fetch and token expiry tracking.
- Cross-cutting: `ruckus_one/logging_config.py`
  - request/response formatting and sensitive header masking.
- Domain/resource layer:
  - `BaseResource` (generic CRUD + pagination + name caching) in `ruckus_one/resources/base.py`
  - Specialized resources:
    - `VenuesResource` (country validation)
    - `WiFiNetworksResource` (SSID/type payload restructuring + activation + venue settings)
    - `APsResource` (AP operations + neighbor scan orchestration + AP networkSettings)
    - `APGroupsResource` (AP group CRUD + network activation/deactivation)
    - `RadiusServerProfilesResource` (list + exact name lookup via `/radiusServerProfiles/query`)
    - `DpskServicesResource` (list via `/dpskServices/query`; exact `get_by_name` via deprecated `GET /dpskServices?name=...`)
    - `ActivitiesResource` (polling async request status)

### Why this structure
- Shared “resource” behaviors are implemented once (`BaseResource`) where endpoint shapes match a generic CRUD + list/query pattern.
- For endpoints that don’t fit the generic CRUD shape (APs and AP groups), bespoke resource classes are used.
- Centralizing error parsing in the client ensures consistent exception types across all resources.

## 3) Key Components (modules/classes)

### `ruckus_one/client.py`
- Class: `RuckusOneClient`
  - What it does:
    - Owns HTTP session and composes request headers (auth + optional delegated tenant header).
    - Provides HTTP convenience wrappers (`get/post/put/patch/delete`) and a common error handler.
    - Instantiates resource objects and exposes them as attributes.
  - Inputs:
    - `region`, `tenant_id`, `client_id`, `client_secret`
    - optional: `delegated_tenant_id`, `timeout`, `max_retries`, `enable_retry`, `log_level`
  - Outputs:
    - Resource attributes: `venues`, `aps`, `wifi_networks`, `ap_groups`, `activities`
    - HTTP methods return parsed JSON dicts (or `None` if no content).
  - Key internals:
    - `_request(...)`: normalizes paths to `base_url + path` unless given an absolute URL.
    - `_request_with_retry(...)`: manual exponential backoff for `RuckusOneConnectionError` only.
    - `_handle_response(...)` + `_raise_error_for_status(...)`:
      - maps HTTP status to exception types (401/403/404/422/400/>=400)
      - extracts helpful error messages using `_extract_error_messages(...)`
      - clears token cache on 401 (`self.auth.clear_token()`).

### `ruckus_one/auth.py`
- Class: `OAuth2TokenManager`
  - What it does:
    - Performs OAuth2 client-credentials flow token fetch for the given `region` + `tenant_id`.
    - Caches access token in memory and refreshes it before expiry (expiry minus `token_refresh_buffer`).
  - Inputs:
    - `region`, `tenant_id`, `client_id`, `client_secret`, optional `token_refresh_buffer`
  - Outputs:
    - `get_token()` returns a string token
    - `get_headers()` returns `{"Authorization": f"Bearer {token}"}`
  - Gotcha:
    - Cache is per process only (no persistence across runs).

### `ruckus_one/logging_config.py`
- Functions:
  - `set_log_level(level)`: configures `ruckus_one` logger level and adds a `StreamHandler` if no handlers exist; disables `httpx`/`httpcore` loggers.
  - `mask_sensitive_headers(headers)`: masks values for `authorization`, `x-api-key`, `x-rks-tenantid`, `cookie`.
  - `format_request_body(body)` / `format_response_body(body)`: pretty prints JSON-like structures and truncates long responses.

### `ruckus_one/exceptions.py`
- Exception hierarchy (all derive from `RuckusOneAPIError`):
  - `RuckusOneAuthenticationError` (401)
  - `RuckusOnePermissionError` (403)
  - `RuckusOneNotFoundError` (404)
  - `RuckusOneValidationError` (422) includes `.errors` list
  - `RuckusOneConnectionError` (network/`httpx.RequestError`) includes `.original_error`
  - `RuckusOneAsyncOperationError` for polling failures/timeouts includes `.request_id` and optional `.response_data`

### `ruckus_one/resources/base.py`
- Class: `BaseResource`
  - What it does:
    - Implements generic CRUD-like operations for endpoints that behave like:
      - list/all: `GET {path}?limit=&offset=`
      - get-by-id: `GET {path}/{id}`
      - create: `POST {path}` with JSON body
      - update: `PUT {path}/{id}`
      - delete: `DELETE {path}/{id}`
    - Implements pagination in `all()` via `offset/limit` loop.
    - Implements `filter(**kwargs)` using a “query endpoint” pattern:
      - tries `POST {path}/query` with `json=kwargs`
      - falls back to `GET {path}` with `params=kwargs` only if `POST` raised `RuckusOneNotFoundError`.
    - Implements name caching in `get_by_name(...)` with `_name_cache`.
  - Convention:
    - Subclasses set class attributes:
      - `_required_fields_create`
      - `_required_fields_update`
    - `create()` and `update()` enforce these via `_validate_required(...)`.
  - Inputs/outputs:
    - Consumes a dict payload (kwargs) and returns a dict/optional dict matching API responses.

### `ruckus_one/resources/venues.py`
- Class: `VenuesResource(BaseResource)`
  - What it does:
    - Adds minimal pre-validation for `address.country` using `pycountry`.
    - Implements `create()` override to validate country name when present.
  - Validation behavior:
    - Rejects ISO alpha-2/alpha-3 inputs (2–3 letters) by checking if `pycountry` lookup matches ISO codes.
    - Requires full country name matching by case-insensitive equality to the country `.name`.
  - Other behavior:
    - Inherits BaseResource pagination/CRUD/filter patterns.

### `ruckus_one/resources/wifi_networks.py`
- Class: `WiFiNetworksResource(BaseResource)`
  - What it does:
    - Validates Wi-Fi network creation input shape.
    - Restructures payload to meet API expectations:
      - `ssid` is accepted as a top-level convenience arg but is nested into `wlan["ssid"]`
      - `wlan["type"]` is set from top-level `type` (and `type` is also included at top-level for the base required-field validation).
    - Validates `type` against `_VALID_NETWORK_TYPES = ["aaa","dpsk","guest","hotspot20","open","psk"]` (lowercase only).
    - Provides network activation/deactivation + venue-specific settings APIs:
      - `activate_at_venue(venue_id, network_id)` -> `POST /networkActivations`
      - `deactivate_at_venue(network_venue_id|list)` -> `DELETE /networkActivations` with JSON array
      - `list_venue_networks(venue_id, network_id=None)` -> `POST /networkActivations/query`
      - `get_venue_settings(venue_id, network_id)` -> `GET /venues/{venue}/wifiNetworks/{network}/settings`
      - `update_venue_settings(...)` -> `PUT .../settings`
  - Gotchas:
    - `create()`’s payload rework runs before base required-field validation, so some error messages are “wlan.ssid is required” rather than “Missing required fields...”.

### `ruckus_one/resources/aps.py`
- Class: `APsResource` (custom; does not inherit `BaseResource`)
  - What it does:
    - AP CRUD-ish operations and neighbor scan:
      - `get_by_serial(venue_id, serial_number)` -> `GET /venues/aps/{serialNumber}` (note: `venue_id` currently unused)
      - `list(venue_id=None, **filters)` -> `GET /venues/aps?venueId=...` (plus query params from `filters`)
      - `create(venue_id, **kwargs)` -> `POST /venues/aps` with JSON array (API expects an array of AP objects)
      - `update(venue_id, serial_number, data)` -> currently attempts `PUT /venues/aps/{serialNumber}` with venueId + serialNumber in body; PATCH fallback is effectively unimplemented.
      - `delete(venue_id, serial_number|list)` -> `DELETE /venues/aps` with JSON array body of serial numbers
    - Neighbor scan workflow:
      - `collect_neighbors(venue_id, serial_number, neighbor_type="LLDP_NEIGHBOR")`:
        - triggers scan asynchronously via `PATCH /venues/{venue}/aps/{serial}/neighbors`
        - payload: `{"status":"CURRENT","type": neighbor_type}`
      - `get_lldp_neighbors(venue_id, serial_number, page, page_size, sort_field, sort_order)`:
        - queries neighbors via `POST /venues/{venue}/aps/{serial}/neighbors/query`
        - payload hardcodes `filters=[{"type":"LLDP_NEIGHBOR"}]` (does not switch filters based on the scan type)
        - returns `[]` if the API reports `WIFI-10498` “no detected neighbor data”
    - Network settings:
      - `get_network_settings(venue_id, serial_number)` -> `GET /venues/{venue}/aps/{serial}/networkSettings`
      - `update_network_settings(...)` -> `PUT .../networkSettings`

### `ruckus_one/resources/ap_groups.py`
- Class: `APGroupsResource` (custom; does not inherit `BaseResource`)
  - What it does:
    - Uses assumed endpoints for AP groups:
      - base path: `/venues/{venue_id}/apGroups`
      - `list(venue_id)` -> `GET {base}`
      - `get(venue_id, id)` -> `GET {base}/{id}`
      - `get_by_name(venue_id, name, use_cache=True)` -> client-side exact match over `list()` results; caches `venue_id -> name -> id`.
    - CRUD:
      - `create(venue_id, **kwargs)` requires `_required_fields_create=["name"]`
      - `update(venue_id, id, **kwargs)` requires `name` and filters payload keys to `["apSerialNumbers","description","name"]`.
    - Network activation:
      - `activate_network(venue_id, ap_group_id, network_id)`:
        - `PUT /venues/{venue}/wifiNetworks/{network}/apGroups/{apGroupId}` with JSON `{}`.
      - `deactivate_network(venue_id, ap_group_id, network_id)`:
        - `DELETE` on the same endpoint.

## 4) Data Flow (end-to-end journeys)

### Journey A: Client initialization + venue discovery by name
1. User constructs `client = RuckusOneClient(region, tenant_id, client_id, client_secret, ...)`.
2. `RuckusOneClient.__init__`:
   - instantiates `OAuth2TokenManager(...)`
   - sets `base_url` from token manager’s region mapping
   - creates `httpx.Client(base_url=..., timeout=...)`
   - instantiates resource wrappers:
     - `client.venues = VenuesResource(self)`
     - `client.aps = APsResource(self)` etc.
3. User calls `client.venues.get_by_name("Main Office")`.
4. `VenuesResource.get_by_name(...)` delegates to `BaseResource.get_by_name(...)`:
   - checks `_name_cache` first; if missing:
   - calls `BaseResource.get(name=..., ...)` without `id`
5. `BaseResource.get(...)` when filtering:
   - calls `BaseResource.all()` to retrieve all venues via pagination
   - runs `_filter_items_client_side(all_items, name=...)` with case-insensitive string comparisons
   - expects exactly one match; otherwise raises `RuckusOneNotFoundError` or `ValueError`.
6. Network/auth behavior during requests:
   - `RuckusOneClient._get_headers()` asks `OAuth2TokenManager.get_headers()`
   - `get_headers()` calls `get_token()` which:
     - uses cached token if not expired
     - otherwise calls `_fetch_token()` (HTTP POST to `/oauth2/token/{tenant_id}`)
   - request proceeds through `_request_with_retry()` and `_handle_response()` for consistent error mapping.

### Journey B: Create a Wi-Fi network + activate it + poll async completion
1. User constructs client as above.
2. User calls `client.wifi_networks.create(name=..., type="psk", ssid="GuestSSID", wlan={...?})`.
3. `WiFiNetworksResource.create(...)`:
   - validates `type` is in `_VALID_NETWORK_TYPES` and is lowercase
   - accepts convenience `ssid` or reads `wlan["ssid"]`
   - restructures payload:
     - ensures `wlan` exists as dict
     - nests `ssid` into `wlan["ssid"]`
     - sets `wlan["type"] = kwargs["type"]`
   - passes final payload to `BaseResource.create(...)`:
     - enforces `_required_fields_create=["name","type","wlan"]`
     - calls `client.post("/networks", json=payload)`
4. If the API is async, response may include `requestId`.
5. User triggers activation:
   - `client.wifi_networks.activate_at_venue(venue_id, network_id)`
   - calls `POST /networkActivations` with `{venueId, networkId}`
6. If activation returns a `requestId`, user polls:
   - `client.activities.wait_for_completion(request_id, timeout, poll_interval)`
   - `ActivitiesResource.wait_for_completion(...)` loops:
     - fetches `/activities/{requestId}`
     - checks status:
       - `SUCCESS` -> return final activity payload
       - failure statuses -> parse error payload and raise `RuckusOneAsyncOperationError`
     - raises timeout error if elapsed exceeds `timeout`.

### Journey C (AP neighbor scan orchestration)
1. User triggers scan: `client.aps.collect_neighbors(venue_id, serial, neighbor_type=...)`
   - PATCH `/venues/{venue}/aps/{serial}/neighbors` with `status CURRENT` and `type neighbor_type`
2. After some delay, user queries: `client.aps.get_lldp_neighbors(...)`
   - POST `/venues/{venue}/aps/{serial}/neighbors/query`
   - queries `filters=[{"type":"LLDP_NEIGHBOR"}]` (hardcoded)
   - if API errors with `WIFI-10498`, returns `[]` instead of raising.

## 5) Key Abstractions & Conventions

### Resource classes and method shapes
- `BaseResource`-based resources (venues, wifi_networks):
  - `all()` returns `List[Dict[str, Any]]` and auto-paginates.
  - `get(id=...)` does direct `GET {path}/{id}`
  - `get(name=...)` is “filter by client-side scanning all pages” (not server filtering).
  - `filter(**kwargs)` prefers `{path}/query` (POST) and falls back to `{path}` (GET params) only on 404.
  - `create(**kwargs)` and `update(id, data)` enforce `_required_fields_*`.
- Custom resources (aps, ap_groups, activities) implement endpoint-specific logic.

### Validation conventions
- Venues:
  - validates `address.country` is a full name, rejects ISO alpha2/alpha3.
- Wi-Fi networks:
  - validates network `type` against allowlist; requires SSID nested into `wlan`.

### Name/ID caching conventions
- `BaseResource.get_by_name(...)` caches `name -> id` in `_name_cache`.
- `APGroupsResource.get_by_name(...)` caches `venue_id -> {name -> id}`.

### Logging conventions
- All HTTP calls pass through `RuckusOneClient._request(...)`, which logs:
  - method + URL
  - query params (if any)
  - headers with sensitive masking
  - formatted request body (if JSON/data)
  - response status + truncated response body.

## 6) External Dependencies

### Runtime dependencies (from `pyproject.toml`)
- `httpx`:
  - HTTP transport (`httpx.Client`, `httpx.post` for OAuth token fetching)
- `pycountry`:
  - `VenuesResource` country name validation
- `pydantic`:
  - declared but not used in the current codepaths (likely reserved for future schema work).

### Test/development dependencies
- `pytest`, `pytest-mock`
- `responses` (HTTP mocking)
- `mypy`, `types-requests`
- `flake8`, `black` (formatting/lint)

### External API/service roles
- Ruckus One API:
  - OAuth token endpoint: `/oauth2/token/{tenantId}`
  - Resources:
    - `/venues`, `/venues/aps`, `/networks`, `/networkActivations`, and AP neighbor/query endpoints
    - `/activities/{requestId}` for async polling.

## 7) Entry Points / How Execution Starts

### Library usage (primary)
- Import and instantiate:
  - `from ruckus_one import RuckusOneClient`
  - call methods via resource attributes.

### Example script
- `test.py`:
  - sets `log_level`, hardcodes credential placeholders, creates `RuckusOneClient`, then calls `client.venues.get_by_name(...)`.

### Test runner
- `pytest` suite under `tests/` (unit tests use `unittest.mock` to isolate HTTP).
- Repo `README.md` documents `make tests` usage.

## 8) Notable Quirks / Gotchas

- Typing vs runtime shape mismatch:
  - `RuckusOneClient.post/put/delete` JSON type hints are `Optional[Dict]`, but several resources pass JSON arrays/lists (e.g. AP create sends `json=[ap_data]`; AP delete sends `json=[serialNumbers]`; Venues/WiFi uses dicts).
  - Runtime works because `httpx` accepts JSON-serializable types, but strict type checking may complain.
- `APsResource.update(...)` fallback is effectively unimplemented:
  - attempts `PUT` and has a placeholder `PATCH` fallback but only raises an error afterwards.
  - If `PUT` is not available or fails, `update()` may not behave as expected.
- Neighbor scan filter mismatch:
  - `collect_neighbors(..., neighbor_type="RF_NEIGHBOR")` can request RF neighbor collection,
  - but `get_lldp_neighbors(...)` always queries with `filters=[{"type":"LLDP_NEIGHBOR"}]` (hardcoded).
- `get_by_serial(venue_id, serial_number)` does not use `venue_id` at all (kept for backward compatibility in signature).
- `BaseResource.filter(**kwargs)` fallback logic:
  - only falls back from `POST {path}/query` to `GET {path}` on `RuckusOneNotFoundError` (404).
  - If the API uses different error semantics, you may not get a fallback.
- Retry scope:
  - `_request_with_retry` retries only on connection errors (`RuckusOneConnectionError`).
  - 401 token-expiry clearing happens, but the request itself isn’t retried automatically after token refresh.
- Package metadata mismatch:
  - `pyproject.toml` version is `0.1.1`, while `ruckus_one/__init__.py` sets `__version__ = "0.1.0"`.
- Async polling error parsing:
  - `ActivitiesResource` expects `activity["error"]` to be a JSON string containing an `errors` array of JSON-ish items; it attempts to parse into human-readable messages and then raises `RuckusOneAsyncOperationError`.

