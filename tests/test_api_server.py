"""Unit tests for the FastAPI observability endpoints."""

import pytest
from fastapi.testclient import TestClient

from wsb_agent.api.server import app

# Create a test client
client = TestClient(app)

def test_health_check_endpoint():
    """Verify the /health endpoint returns expected schema."""
    # Note: Because the TestClient does not run the `lifespan` block by default 
    # without an async context manager, the globals might be None. We test the structure.
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "active"
    assert "version" in data
    assert "database_connected" in data
    assert "broker_type" in data

def test_signals_endpoint_uninitialized():
    """Verify /signals returns 500 when DB is not injected via lifespan."""
    response = client.get("/signals")
    assert response.status_code == 500
    assert "Database not initialized" in response.json()["detail"]

def test_portfolio_endpoint_uninitialized():
    """Verify /portfolio returns 500 when Broker is not injected via lifespan."""
    response = client.get("/portfolio")
    assert response.status_code == 500
    assert "Broker not initialized" in response.json()["detail"]
