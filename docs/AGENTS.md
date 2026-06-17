# Agent guide — python-ruckus-one

## What this repo is

Python client library for the Ruckus One REST API. Resource-oriented wrappers
cover venues, APs, Wi-Fi networks, AP groups, radius/DPSK profiles, and async
activity polling. Does **not** own workflows or NetBox integration.

## Package layout (`ruckus_one/`)

| Path | Purpose |
|------|---------|
| `ruckus_one/client.py` | `RuckusOneClient` — HTTP session, auth, resource composition |
| `ruckus_one/auth.py` | OAuth2 client-credentials token manager (in-memory cache) |
| `ruckus_one/http.py` | *(via client)* — retries, error parsing, header masking |
| `ruckus_one/logging_config.py` | Request/response logging, sensitive header masking |
| `ruckus_one/exceptions.py` | `RuckusOneAPIError` hierarchy |
| `ruckus_one/resources/base.py` | Generic CRUD, pagination, name caching |
| `ruckus_one/resources/venues.py` | Venues + country validation (`pycountry`) |
| `ruckus_one/resources/wifi_networks.py` | Wi-Fi CRUD, activation, venue settings |
| `ruckus_one/resources/aps.py` | AP CRUD, neighbor scan, network settings |
| `ruckus_one/resources/ap_groups.py` | AP group CRUD + network activation |
| `ruckus_one/resources/activities.py` | Async `requestId` polling |
| `ruckus_one/resources/radius_server_profiles.py` | Radius profile query |
| `ruckus_one/resources/dpsk_services.py` | DPSK service query |

Repo root: `tests/`, `Makefile`, `pyproject.toml`.

## Conventions

- **Entry point:** `from ruckus_one import RuckusOneClient`; resources via client attributes.
- **Public resource methods** follow keyword-only style where added; many `BaseResource` methods accept `**kwargs` for filter/create payloads.
- **Typed dict responses** — resources return `dict` payloads from the API (not raw JSON-only like cnMaestro SDK).
- **Async operations:** create/update/activate may return `requestId`; poll via `client.activities.wait_for_completion(...)`.
- **BaseResource** subclasses set `_required_fields_create` / `_required_fields_update` for validation.

## Where to look

- **Index:** [INDEX.md](INDEX.md)
- **Memory:** [.agents/memory/python-ruckus-one-repository-memory.md](../.agents/memory/python-ruckus-one-repository-memory.md)

## Starting a new task

1. Read `.agents/memory/python-ruckus-one-repository-memory.md` (architecture, journeys, gotchas).
2. Run `make tests` before opening a PR.

## Testing

- Full suite: `make tests` (`lint`, `type-check`, `unit-tests`).
- Tests in `tests/` with `pytest` and `responses` / mocks for HTTP isolation.
