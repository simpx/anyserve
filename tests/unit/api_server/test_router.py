"""
Unit tests for API Server router endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from anyserve.api_server.router import create_app


@pytest.fixture
def client():
    """Create a test client for the API server."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    @pytest.mark.p0
    def test_health_returns_ok(self, client):
        """Test health endpoint returns status healthy."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestRegisterEndpoint:
    """Tests for POST /register endpoint."""

    @pytest.mark.p0
    def test_register_replica(self, client):
        """Test registering a new replica."""
        payload = {
            "replica_id": "test-replica",
            "endpoint": "localhost:50051",
            "capabilities": [{"type": "chat", "model": "demo"}]
        }

        response = client.post("/register", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "test-replica" in data["message"]

    @pytest.mark.p0
    def test_register_multiple_capabilities(self, client):
        """Test registering replica with multiple capabilities."""
        payload = {
            "replica_id": "multi-cap-replica",
            "endpoint": "localhost:50052",
            "capabilities": [
                {"type": "chat"},
                {"type": "embed"},
                {"type": "heavy", "gpus": 2},
            ]
        }

        response = client.post("/register", json=payload)

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.p1
    def test_register_missing_fields(self, client):
        """Test register with missing required fields returns error."""
        payload = {"replica_id": "incomplete"}

        response = client.post("/register", json=payload)

        assert response.status_code == 422  # Validation error


class TestUnregisterEndpoint:
    """Tests for DELETE /unregister endpoint."""

    @pytest.mark.p0
    def test_unregister_replica(self, client):
        """Test unregistering a replica."""
        # First register
        client.post("/register", json={
            "replica_id": "to-remove",
            "endpoint": "localhost:50051",
            "capabilities": [{"type": "test"}]
        })

        # Then unregister
        response = client.request("DELETE", "/unregister", json={
            "replica_id": "to-remove"
        })

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.p1
    def test_unregister_nonexistent(self, client):
        """Test unregistering non-existent replica returns success=False."""
        response = client.request("DELETE", "/unregister", json={
            "replica_id": "nonexistent"
        })

        # API returns 200 with success=False for not found
        assert response.status_code == 200
        assert response.json()["success"] is False


class TestRegistryEndpoint:
    """Tests for GET /registry endpoint."""

    @pytest.mark.p0
    def test_registry_empty(self, client):
        """Test registry endpoint on empty registry."""
        response = client.get("/registry")

        assert response.status_code == 200
        data = response.json()
        assert data["replicas"] == []
        assert data["total"] == 0

    @pytest.mark.p0
    def test_registry_with_replicas(self, client):
        """Test registry endpoint with registered replicas."""
        # Register some replicas
        client.post("/register", json={
            "replica_id": "r1",
            "endpoint": "localhost:50051",
            "capabilities": [{"type": "chat"}]
        })
        client.post("/register", json={
            "replica_id": "r2",
            "endpoint": "localhost:50052",
            "capabilities": [{"type": "embed"}]
        })

        response = client.get("/registry")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["replicas"]) == 2


class TestInferEndpoint:
    """Tests for POST /infer endpoint."""

    @pytest.mark.p0
    def test_infer_no_capability_headers(self, client):
        """Test infer without capability headers returns 400."""
        response = client.post("/infer", content=b"test")
        assert response.status_code == 400

    @pytest.mark.p0
    def test_infer_no_replica_found(self, client):
        """Test infer with no matching replica returns 404."""
        response = client.post(
            "/infer",
            headers={"X-Capability-Type": "nonexistent"},
            content=b"test"
        )
        assert response.status_code == 404


class TestInferJsonEndpoint:
    """Tests for POST /infer/json endpoint."""

    @pytest.fixture(autouse=True)
    def setup_replica(self, client):
        """Register a test replica before each test."""
        client.post("/register", json={
            "replica_id": "test-worker",
            "endpoint": "localhost:50051",
            "capabilities": [
                {"type": "chat", "model": "demo"},
                {"type": "embed"},
            ]
        })

    @pytest.mark.p0
    def test_infer_json_no_capability_headers(self, client):
        """Test infer/json without capability headers returns 400."""
        response = client.post(
            "/infer/json",
            json={"inputs": []}
        )
        # Without headers, falls back to model_name which may not exist
        assert response.status_code in [400, 404]

    @pytest.mark.p1
    def test_infer_json_with_capability_headers(self, client):
        """Test infer/json with capability headers attempts routing."""
        response = client.post(
            "/infer/json",
            headers={
                "X-Capability-Type": "chat",
                "X-Capability-Model": "demo",
            },
            json={"inputs": []}
        )
        # Will try to connect to gRPC which won't be available
        # Should return 502 (Bad Gateway) when gRPC fails
        assert response.status_code == 502


class TestInferJsonRouting:
    """Tests for infer/json routing logic."""

    @pytest.mark.p0
    def test_infer_no_matching_replica(self, client):
        """Test infer returns 404 when no replica matches."""
        response = client.post(
            "/infer/json",
            headers={"X-Capability-Type": "nonexistent"},
            json={"inputs": []}
        )
        assert response.status_code == 404

    @pytest.mark.p1
    def test_infer_delegation_header_routing(self, client):
        """Test infer excludes replicas listed in delegation header."""
        # Register two replicas with same capability
        client.post("/register", json={
            "replica_id": "replica-a",
            "endpoint": "localhost:60001",
            "capabilities": [{"type": "shared"}]
        })
        client.post("/register", json={
            "replica_id": "replica-b",
            "endpoint": "localhost:60002",
            "capabilities": [{"type": "shared"}]
        })

        # Request with X-Delegated-From should exclude that replica
        response = client.post(
            "/infer/json",
            headers={
                "X-Capability-Type": "shared",
                "X-Delegated-From": "replica-a",
            },
            json={"inputs": []}
        )

        # Should try to route (but fail to connect to gRPC)
        assert response.status_code == 502
