"""Tests for activities resource."""

from unittest.mock import MagicMock

import pytest

from ruckus_one.exceptions import RuckusOneAsyncOperationError, RuckusOneNotFoundError
from ruckus_one.resources.activities import ActivitiesResource


def test_activities_resource_initialization(mock_client):
    """Test ActivitiesResource initialization."""
    resource = ActivitiesResource(mock_client)
    assert resource.client == mock_client


def test_activities_get(mock_client):
    """Test getting activity status."""
    mock_client.get.return_value = {
        "requestId": "req_123",
        "status": "SUCCESS",
        "message": "Operation completed",
    }

    resource = ActivitiesResource(mock_client)
    activity = resource.get("req_123")

    assert activity["status"] == "SUCCESS"
    mock_client.get.assert_called_once_with("/activities/req_123")


def test_activities_get_not_found(mock_client):
    """Test getting activity when not found."""
    mock_client.get.return_value = None

    resource = ActivitiesResource(mock_client)
    with pytest.raises(RuckusOneNotFoundError):
        resource.get("invalid_req")


def test_activities_wait_for_completion_success(mock_client):
    """Test waiting for activity completion (success)."""
    mock_client.get.return_value = {
        "requestId": "req_123",
        "status": "SUCCESS",
        "message": "Operation completed",
    }

    resource = ActivitiesResource(mock_client)
    activity = resource.wait_for_completion("req_123", timeout=10.0, poll_interval=0.1)

    assert activity["status"] == "SUCCESS"


def test_activities_wait_for_completion_failed(mock_client):
    """Test waiting for activity completion (failed)."""
    mock_client.get.return_value = {
        "requestId": "req_123",
        "status": "FAILED",
        "message": "Operation failed",
    }

    resource = ActivitiesResource(mock_client)
    with pytest.raises(RuckusOneAsyncOperationError) as exc_info:
        resource.wait_for_completion("req_123", timeout=10.0, poll_interval=0.1)

    assert exc_info.value.request_id == "req_123"
