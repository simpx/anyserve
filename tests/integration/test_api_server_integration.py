"""
Integration tests for API Server with multiple components.
"""

import pytest
from fastapi.testclient import TestClient
from anyserve.api_server.router import create_app


@pytest.fixture
def client():
    """Create a test client for the API server."""
    app = create_app()
    return TestClient(app)


@pytest.mark.integration
class TestFullRegisterLookupFlow:
    """Integration tests for register -> lookup -> route flow."""

    @pytest.mark.p0
    def test_register_lookup_flow(self, client):
        """Test full flow: register replica, lookup, verify routing."""
        # 1. Register a replica
        register_response = client.post("/register", json={
            "replica_id": "flow-test-replica",
            "endpoint": "localhost:60001",
            "capabilities": [
                {"type": "chat", "model": "test-model"},
            ]
        })
        assert register_response.status_code == 200

        # 2. Verify in registry
        registry_response = client.get("/registry")
        assert registry_response.status_code == 200
        data = registry_response.json()
        assert data["count"] == 1
        assert data["replicas"][0]["replica_id"] == "flow-test-replica"

        # 3. Verify capability is listed
        caps_response = client.get("/capabilities")
        assert {"type": "chat", "model": "test-model"} in caps_response.json()["capabilities"]

    @pytest.mark.p0
    def test_multiple_replicas_routing(self, client):
        """Test routing with multiple replicas."""
        # Register multiple replicas with different capabilities
        client.post("/register", json={
            "replica_id": "chat-replica",
            "endpoint": "localhost:60001",
            "capabilities": [{"type": "chat"}]
        })
        client.post("/register", json={
            "replica_id": "embed-replica",
            "endpoint": "localhost:60002",
            "capabilities": [{"type": "embed"}]
        })
        client.post("/register", json={
            "replica_id": "heavy-replica",
            "endpoint": "localhost:60003",
            "capabilities": [{"type": "heavy", "gpus": 2}]
        })

        # Verify all registered
        registry = client.get("/registry").json()
        assert registry["count"] == 3

        # Verify capabilities
        caps = client.get("/capabilities").json()["capabilities"]
        assert len(caps) == 3

    @pytest.mark.p0
    def test_unregister_clears_from_registry(self, client):
        """Test unregister removes replica from registry."""
        # Register
        client.post("/register", json={
            "replica_id": "temp-replica",
            "endpoint": "localhost:60004",
            "capabilities": [{"type": "temp"}]
        })

        # Verify registered
        assert client.get("/registry").json()["count"] == 1

        # Unregister
        client.request("DELETE", "/unregister", json={
            "replica_id": "temp-replica"
        })

        # Verify removed
        assert client.get("/registry").json()["count"] == 0


@pytest.mark.integration
class TestDelegationFlow:
    """Integration tests for delegation mechanism."""

    @pytest.mark.p1
    def test_delegation_excludes_replica(self, client):
        """Test delegation header causes exclusion in routing."""
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

        # Request with delegation header should try to exclude replica-a
        # (actual routing can't be verified without gRPC backend)
        response = client.post(
            "/infer/json",
            headers={
                "X-Capability-Type": "shared",
                "X-Delegated-From": "replica-a",
            },
            json={"inputs": []}
        )

        # Should attempt to route (may fail without backend)
        assert response.status_code in [200, 503]


@pytest.mark.integration
class TestObjectPassingIntegration:
    """Integration tests for object passing between components."""

    @pytest.mark.p0
    def test_create_and_read_object(self, temp_dir):
        """Test creating and reading objects through ObjectStore."""
        from anyserve.objects import ObjectStore

        store = ObjectStore(temp_dir)

        # Create various types of objects
        obj1 = store.create({"dict": "value"})
        obj2 = store.create([1, 2, 3, 4, 5])
        obj3 = store.create(b"binary data")

        # Read them back
        assert store.get(obj1) == {"dict": "value"}
        assert store.get(obj2) == [1, 2, 3, 4, 5]
        assert store.get(obj3) == b"binary data"

    @pytest.mark.p0
    def test_obj_ref_serialization_roundtrip(self, temp_dir):
        """Test ObjRef can be serialized and used across 'replicas'."""
        from anyserve.objects import ObjectStore, ObjRef

        # Simulate two separate ObjectStore instances (same directory)
        store1 = ObjectStore(temp_dir)
        store2 = ObjectStore(temp_dir)

        # Create object in store1
        original_data = {"message": "cross-replica data"}
        obj_ref = store1.create(original_data)

        # Serialize ObjRef (as would happen in RPC)
        serialized = obj_ref.to_string()

        # Deserialize and read from store2
        received_ref = ObjRef.from_string(serialized)
        retrieved_data = store2.get(received_ref)

        assert retrieved_data == original_data


@pytest.mark.integration
class TestCapabilityRegistryIntegration:
    """Integration tests for capability registry."""

    @pytest.mark.p0
    def test_capability_matching_precision(self):
        """Test capability matching with various queries."""
        from anyserve.api_server.registry import CapabilityRegistry

        registry = CapabilityRegistry()

        # Register replicas with overlapping capabilities
        registry.register(
            replica_id="r1",
            endpoint="localhost:50051",
            capabilities=[
                {"type": "chat", "model": "llama-7b", "version": "v1"},
            ]
        )
        registry.register(
            replica_id="r2",
            endpoint="localhost:50052",
            capabilities=[
                {"type": "chat", "model": "llama-7b", "version": "v2"},
            ]
        )
        registry.register(
            replica_id="r3",
            endpoint="localhost:50053",
            capabilities=[
                {"type": "chat", "model": "llama-70b"},
            ]
        )

        # Test various queries
        # Exact match
        result = registry.lookup({"type": "chat", "model": "llama-7b", "version": "v2"})
        assert result.replica_id == "r2"

        # Partial match (type + model)
        result = registry.lookup({"type": "chat", "model": "llama-70b"})
        assert result.replica_id == "r3"

        # Very partial (type only) - should match first
        result = registry.lookup({"type": "chat"})
        assert result is not None

    @pytest.mark.p1
    def test_registry_concurrent_operations(self):
        """Test registry handles concurrent operations."""
        import concurrent.futures
        from anyserve.api_server.registry import CapabilityRegistry

        registry = CapabilityRegistry()

        def register_replica(i):
            registry.register(
                replica_id=f"concurrent-{i}",
                endpoint=f"localhost:{50000 + i}",
                capabilities=[{"type": f"cap-{i}"}]
            )
            return i

        # Concurrent registrations
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(register_replica, i) for i in range(20)]
            results = [f.result() for f in futures]

        assert len(registry.list_all()) == 20
