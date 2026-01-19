# Ruckus One Python Client

A Python client library for the Ruckus One API.

## Features

- **OAuth2 Authentication**: Automatic token management with caching and refresh
- **Resource-Based API**: Intuitive object-oriented interface (client.venues.all(), client.aps.get(), etc.)
- **Full API Coverage**: Access to all Ruckus One API endpoints
- **Type Hints**: Full type annotations for better IDE support
- **Error Handling**: Custom exceptions for different error scenarios
- **Retry Logic**: Automatic retry with exponential backoff
- **Client-Side Validation**: Pre-validation of required fields and data formats
- **Address Validation**: Country name validation using full country names (rejects ISO codes)
- **Async Operations**: Support for asynchronous API operations with polling
- **Multi-Region Support**: Support for US, EU, and Asia regions
- **Logging**: Configurable logging throughout the client
- **Python 3.8+**: Modern Python features and type hints

## Installation

```bash
pip install ruckus-one
```

Or install from source:

```bash
git clone https://github.com/wifinity/python-ruckus-one.git
cd python-ruckus-one
pip install -e .
```

## Quick Start

```python
from ruckus_one import RuckusOneClient

# Initialize the client with your OAuth2 credentials
client = RuckusOneClient(
    region="us",  # or "eu", "asia"
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret"
)

# List all venues
venues = client.venues.all()
print(f"Found {len(venues)} venues")

# Get a specific venue by ID
venue = client.venues.get(id="venue_123")

# Or get by name (with caching)
venue = client.venues.get(name="Main Office")

# List APs in a venue
aps = client.aps.list(venue_id=venue["id"])

# Get AP by serial number
ap = client.aps.get_by_serial(venue_id=venue["id"], serial_number="ABC123")

# Close the client when done
client.close()
```

## Usage

### Client Initialization

```python
from ruckus_one import RuckusOneClient

# Basic initialization
client = RuckusOneClient(
    region="us",
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret"
)

# With custom configuration
client = RuckusOneClient(
    region="us",
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret",
    delegated_tenant_id="delegated_tenant_id",  # For MSP/delegated accounts
    timeout=30.0,
    max_retries=3,
    enable_retry=True,
    log_level="DEBUG",
)
```

### Context Manager

The client can be used as a context manager for automatic cleanup:

```python
with RuckusOneClient(
    region="us",
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret"
) as client:
    venues = client.venues.all()
    # Client is automatically closed when exiting the context
```

### Resource-Based API

The client provides resource objects for intuitive API access:

#### Venues

```python
# Get all venues (automatically handles pagination)
venues = client.venues.all()

# Get a single venue by ID
venue = client.venues.get(id="venue_123")

# Or get by name (with caching)
venue = client.venues.get(name="Main Office")

# Filter venues (client-side filtering)
filtered = client.venues.filter(name="Office")

# Create a venue
new_venue = client.venues.create(
    name="New Office",
    address={
        "street": "123 Main St",
        "city": "San Francisco",
        "state": "CA",
        "zipCode": "94102",
        "country": "United States"  # Must be full country name, not ISO code
    }
)

# Update a venue
updated = client.venues.update("venue_123", {"name": "Updated Office"})

# Delete a venue (or multiple venues)
client.venues.delete("venue_123")
# Or delete multiple:
client.venues.delete(["venue_123", "venue_456"])
```

**Address Validation**: The `address.country` field must be a full country name (e.g., "United States", "United Kingdom"). ISO codes (e.g., "US", "GB") are rejected with a clear error message.

#### APs (Access Points)

```python
# List APs in a venue
aps = client.aps.list(venue_id="venue_123")

# Get AP by serial number
ap = client.aps.get_by_serial(
    venue_id="venue_123",
    serial_number="ABC123"
)

# Create/add an AP to a venue
# Note: Both serialNumber and name are required
new_ap = client.aps.create(
    venue_id="venue_123",
    name="R550 Access Point",  # Required
    serialNumber="ABC123",  # Required
    description="Office AP",
    tags=["Production"]
)

# Update an AP
updated = client.aps.update(
    venue_id="venue_123",
    serial_number="ABC123",
    data={"name": "Updated AP Name"}
)

# Delete an AP (or multiple APs by serial number)
client.aps.delete(venue_id="venue_123", serial_number="ABC123")
# Or delete multiple:
client.aps.delete(venue_id="venue_123", serial_number=["ABC123", "DEF456"])

# Move an AP to a different venue
client.aps.move(
    venue_id="venue_123",
    serial_number="ABC123",
    target_venue_id="venue_456"
)

# Get LLDP neighbors
# Note: The AP does not always have a live, constant list of neighbors.
# The data must be collected (scanned) before it can be queried.
# First, trigger neighbor collection:
result = client.aps.collect_neighbors(
    venue_id="venue_123",
    serial_number="ABC123",
    neighbor_type="LLDP_NEIGHBOR"  # or "RF_NEIGHBOR"
)
# Wait a moment for the scan to complete (AP performs scan asynchronously),
# then query for neighbors:
neighbors = client.aps.get_lldp_neighbors(
    venue_id="venue_123",
    serial_number="ABC123",
    page=1,
    page_size=25,
    sort_field="deviceName",  # Optional
    sort_order="ASC"  # Optional, "ASC" or "DESC"
)
# If no neighbor data is available, get_lldp_neighbors() returns an empty list
```

#### Wi-Fi Networks

```python
# Get all Wi-Fi networks
networks = client.wifi_networks.all()

# Get a single network by ID
network = client.wifi_networks.get(id="network_123")

# Or get by name (with caching)
network = client.wifi_networks.get(name="Guest Network")

# Filter networks (client-side filtering)
filtered = client.wifi_networks.filter(ssid="Guest")

# Create a Wi-Fi network
# Note: name, type, and wlan (with ssid) are required
new_network = client.wifi_networks.create(
    name="Guest Network",  # Required
    type="psk",  # Required (one of: aaa, dpsk, guest, hotspot20, open, psk)
    ssid="GuestSSID",  # Required (will be nested in wlan object)
    # ... other network configuration
)

# Update a network
updated = client.wifi_networks.update(
    "network_123",
    {"ssid": "UpdatedSSID"}
)

# Delete a network
client.wifi_networks.delete("network_123", deep=True)

# List networks activated at a venue
venue_networks = client.wifi_networks.list_venue_networks(venue_id="venue_123")

# Activate network at a venue
result = client.wifi_networks.activate_at_venue(
    venue_id="venue_123",
    network_id="network_123"
)

# Deactivate network at venue (using network-venue association ID)
client.wifi_networks.deactivate_at_venue("network_venue_association_id")
```

#### AP Groups

```python
# List AP groups in a venue
ap_groups = client.ap_groups.list(venue_id="venue_123")

# Get AP group by ID
ap_group = client.ap_groups.get(venue_id="venue_123", id="apgroup_123")

# Or get by name (with caching)
ap_group = client.ap_groups.get_by_name(
    venue_id="venue_123",
    name="Main AP Group"
)

# Create an AP group
# Note: name is required
new_group = client.ap_groups.create(
    venue_id="venue_123",
    name="New AP Group"  # Required
)

# Update an AP group
updated = client.ap_groups.update(
    venue_id="venue_123",
    id="apgroup_123",
    data={"name": "Updated Group"}
)

# Activate a network on an AP group
client.ap_groups.activate_network(
    venue_id="venue_123",
    ap_group_id="apgroup_123",
    network_id="network_123"
)

# Deactivate a network from an AP group
client.ap_groups.deactivate_network(
    venue_id="venue_123",
    ap_group_id="apgroup_123",
    network_id="network_123"
)
```

#### Activities (Async Operations)

Many create/update operations return a `requestId` for async processing. Use the activities resource to poll for completion:

```python
# Create a venue (may return requestId)
result = client.venues.create(name="New Venue", address={"country": "United States"})
request_id = result.get("requestId")

if request_id:
    # Poll until completion
    activity = client.activities.wait_for_completion(
        request_id=request_id,
        timeout=300.0,  # 5 minutes
        poll_interval=2.0  # Poll every 2 seconds
    )
    
    # Check activity status
    if activity.get("status") == "SUCCESS":
        print("Operation completed successfully")
    else:
        print(f"Operation failed: {activity.get('message')}")

# Or get activity status directly
activity = client.activities.get(request_id="request_123")
```

### Low-Level API Access

For endpoints not covered by resources, use the low-level HTTP methods:

```python
# GET request
result = client.get("/custom/endpoint", params={"key": "value"})

# POST request
result = client.post("/custom/endpoint", json={"data": "value"})

# PUT request
result = client.put("/custom/endpoint", json={"data": "value"})

# DELETE request
result = client.delete("/custom/endpoint")
```

### Error Handling

The client raises specific exceptions for different error scenarios:

```python
from ruckus_one import (
    RuckusOneClient,
    RuckusOneAuthenticationError,
    RuckusOneNotFoundError,
    RuckusOnePermissionError,
    RuckusOneValidationError,
    RuckusOneAPIError,
    RuckusOneConnectionError,
)

client = RuckusOneClient(
    region="us",
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret"
)

try:
    venue = client.venues.get(id="venue_123")
except RuckusOneNotFoundError:
    print("Venue not found")
except RuckusOneAuthenticationError:
    print("Authentication failed - check your tenant_id, client_id, and client_secret")
except RuckusOnePermissionError:
    print("Permission denied")
except RuckusOneValidationError as e:
    print(f"Validation error: {e.errors}")
except RuckusOneAPIError as e:
    print(f"API error: {e.status_code} - {e.message}")
except RuckusOneConnectionError:
    print("Connection error - check your network connection")
```

### Retry Logic

The client includes automatic retry logic with exponential backoff for connection errors:

```python
# Retry is enabled by default
client = RuckusOneClient(
    region="us",
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret",
    enable_retry=True,
    max_retries=3
)

# Disable retry for specific operations
client = RuckusOneClient(
    region="us",
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret",
    enable_retry=False
)
```

### Logging

The client supports configurable logging to help debug API interactions. You can set the log level in two ways:

#### Method 1: Client Parameter

```python
# Set log level when creating the client
client = RuckusOneClient(
    region="us",
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret",
    log_level="DEBUG"
)
```

#### Method 2: Module-Level Function

```python
from ruckus_one import set_log_level

# Set log level for all clients
set_log_level("DEBUG")
client = RuckusOneClient(
    region="us",
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret"
)
```

#### Available Log Levels

- `DEBUG` - Detailed information including request/response bodies, headers, and status codes
- `INFO` - General informational messages
- `WARNING` - Warning messages (default)
- `ERROR` - Error messages only
- `CRITICAL` - Critical errors only

#### Debug Logging Output

When `DEBUG` level is enabled, you'll see detailed information about each API request:

```
DEBUG:ruckus_one.client:GET https://api.ruckus.cloud/api/venues
DEBUG:ruckus_one.client:Query parameters: {}
DEBUG:ruckus_one.client:Request headers: {'Authorization': 'Bearer ***', 'Content-Type': 'application/json'}
DEBUG:ruckus_one.client:Response status: 200
DEBUG:ruckus_one.client:Response headers: {'Content-Type': 'application/json', 'Content-Length': '1234'}
DEBUG:ruckus_one.client:Response body: [
  {
    "id": "venue_123",
    "name": "Main Office"
  }
]
```

#### Sensitive Data Masking

For security, sensitive data is automatically masked in logs:
- Authorization tokens: `Bearer abc123` → `Bearer ***`
- API keys and other sensitive headers are masked
- Request/response bodies are logged as-is (be careful with sensitive data in request bodies)

#### Example

```python
from ruckus_one import RuckusOneClient, set_log_level

# Enable debug logging
set_log_level("DEBUG")

client = RuckusOneClient(
    region="us",
    tenant_id="your_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret"
)

# All API calls will now log detailed information
venues = client.venues.all()
```

## Examples

### Working with Venues

```python
# List all venues
venues = client.venues.all()

# Find venue by name
venue = client.venues.get(name="Main Office")

# Create a new venue with address validation
new_venue = client.venues.create(
    name="Branch Office",
    address={
        "street": "456 Branch St",
        "city": "London",
        "zipCode": "SW1A 1AA",
        "country": "United Kingdom"  # Full country name required
    }
)

# Update venue
updated = client.venues.update(
    new_venue["id"],
    {"address": {"city": "Manchester"}}
)

# Delete venue
client.venues.delete(new_venue["id"])
```

### Working with APs

```python
# Get venue first
venue = client.venues.get(name="Main Office")

# List all APs in venue
aps = client.aps.list(venue_id=venue["id"])

# Get specific AP by serial
ap = client.aps.get_by_serial(
    venue_id=venue["id"],
    serial_number="ABC123"
)

# Create a new AP (name and serialNumber are required)
new_ap = client.aps.create(
    venue_id=venue["id"],
    name="R550 Access Point",  # Required
    serialNumber="ABC123",  # Required
    description="Office AP"
)

# Get AP details (includes operational status)
ap = client.aps.get_by_serial(
    venue_id=venue["id"],
    serial_number="ABC123"
)
print(f"AP Status: {ap.get('connectionStatus')}")
print(f"IP Address: {ap.get('ipAddress')}")

# Move AP to different venue
target_venue = client.venues.get(name="Branch Office")
client.aps.move(
    venue_id=venue["id"],
    serial_number="ABC123",
    target_venue_id=target_venue["id"]
)

# Collect and query LLDP neighbors
# The AP needs to actively scan for neighbors first
result = client.aps.collect_neighbors(
    venue_id=venue["id"],
    serial_number="ABC123",
    neighbor_type="LLDP_NEIGHBOR"  # or "RF_NEIGHBOR"
)
# Wait a moment for the scan to complete, then query
import time
time.sleep(2)  # Wait for scan to complete
neighbors = client.aps.get_lldp_neighbors(
    venue_id=venue["id"],
    serial_number="ABC123"
)
for neighbor in neighbors:
    print(f"Neighbor: {neighbor.get('deviceName')} on {neighbor.get('interface')}")
```

### Working with Wi-Fi Networks

```python
# Create a Wi-Fi network (name, type, and wlan with ssid are required)
network = client.wifi_networks.create(
    name="Guest Network",  # Required
    type="psk",  # Required (one of: aaa, dpsk, guest, hotspot20, open, psk)
    ssid="GuestSSID",  # Required (will be nested in wlan object)
    # ... other configuration
)

# Get venue
venue = client.venues.get(name="Main Office")

# Activate network at venue (creates network-venue association)
result = client.wifi_networks.activate_at_venue(
    venue_id=venue["id"],
    network_id=network["id"]
)

# List all networks activated at the venue
venue_networks = client.wifi_networks.list_venue_networks(venue_id=venue["id"])

# Deactivate network at venue
# Note: Use the association ID from list_venue_networks or activate_at_venue response
association_id = result.get("id")
if association_id:
    client.wifi_networks.deactivate_at_venue(association_id)
```

### Working with AP Groups

```python
# Get venue
venue = client.venues.get(name="Main Office")

# Create an AP group (name is required)
ap_group = client.ap_groups.create(
    venue_id=venue["id"],
    name="Production AP Group"  # Required
)

# Get network
network = client.wifi_networks.get(name="Guest Network")

# Activate network on AP group
client.ap_groups.activate_network(
    venue_id=venue["id"],
    ap_group_id=ap_group["id"],
    network_id=network["id"]
)

# List all AP groups in venue
all_groups = client.ap_groups.list(venue_id=venue["id"])
```

### Handling Async Operations

```python
# Create a venue (may return requestId for async processing)
result = client.venues.create(
    name="New Venue",
    address={"country": "United States"}
)

request_id = result.get("requestId")

if request_id:
    # Wait for operation to complete
    activity = client.activities.wait_for_completion(
        request_id=request_id,
        timeout=300.0,  # 5 minutes
        poll_interval=2.0  # Poll every 2 seconds
    )
    
    if activity.get("status") == "SUCCESS":
        print("Venue created successfully")
        venue_id = activity.get("result", {}).get("id")
    else:
        print(f"Operation failed: {activity.get('message')}")
else:
    # Operation completed synchronously
    venue_id = result.get("id")
```

## API Regions

The client supports three regions:

- `"us"` → `https://api.ruckus.cloud` (North America)
- `"eu"` → `https://api.eu.ruckus.cloud` (Europe)
- `"asia"` → `https://api.asia.ruckus.cloud` (Asia)

## Delegated Tenant Support

For MSP (Managed Service Provider) or delegated account scenarios, use the `delegated_tenant_id` parameter:

```python
client = RuckusOneClient(
    region="us",
    tenant_id="msp_tenant_id",
    client_id="your_client_id",
    client_secret="your_client_secret",
    delegated_tenant_id="managed_tenant_id"  # Sets x-rks-tenantid header
)
```

## Client-Side Validation

The client performs pre-validation before making API calls to provide faster, more user-friendly feedback:

### Required Fields

- **Venues**: `name`, `address` are required for creation
- **APs**: `name`, `serialNumber` are required for creation
- **Wi-Fi Networks**: `name`, `type`, and `wlan` (with `ssid`) are required for creation
- **AP Groups**: `name` is required for creation

### Address Validation

The `address.country` field must be a full country name. ISO codes are rejected:

```python
# ✅ Valid
client.venues.create(
    name="Office",
    address={"country": "United States"}
)

# ✅ Valid (case-insensitive)
client.venues.create(
    name="Office",
    address={"country": "united states"}
)

# ❌ Invalid - ISO alpha-2 code
client.venues.create(
    name="Office",
    address={"country": "US"}  # Raises ValueError
)

# ❌ Invalid - ISO alpha-3 code
client.venues.create(
    name="Office",
    address={"country": "USA"}  # Raises ValueError
)
```

## Development

### Running Tests

```bash
# Run all tests
make tests

# Run with coverage
pytest --cov=ruckus_one --cov-report=html
```

### Type Checking

```bash
make type-check
```
