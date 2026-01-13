"""
Unit tests for CapabilityRegistry.
"""

import pytest
from anyserve.api_server.registry import CapabilityRegistry, ReplicaInfo, Capability


class TestCapabilityRegistryRegister:
    """Tests for CapabilityRegistry.register()"""

    @pytest.mark.p0
    def test_register_replica(self, capability_registry):
        """Test registering a new replica."""
        result = capability_registry.register(
            replica_id="replica-1",
            endpoint="localhost:50051",
            capabilities=[
                {"type": "chat", "model": "demo"},
            ]
        )

        assert result is True
        assert "replica-1" in capability_registry._replicas

    @pytest.mark.p0
    def test_register_replica_multiple_capabilities(self, capability_registry):
        """Test registering a replica with multiple capabilities."""
        capabilities = [
            {"type": "chat", "model": "v1"},
            {"type": "chat", "model": "v2"},
            {"type": "embed"},
        ]
        capability_registry.register(
            replica_id="multi-cap",
            endpoint="localhost:50052",
            capabilities=capabilities,
        )

        replica = capability_registry._replicas["multi-cap"]
        assert len(replica.capabilities) == 3

    @pytest.mark.p0
    def test_register_duplicate_updates(self, capability_registry):
        """Test that registering same replica updates capabilities."""
        # First registration
        capability_registry.register(
            replica_id="replica-1",
            endpoint="localhost:50051",
            capabilities=[{"type": "chat"}],
        )

        # Second registration with different capabilities
        capability_registry.register(
            replica_id="replica-1",
            endpoint="localhost:50051",
            capabilities=[{"type": "embed"}, {"type": "heavy"}],
        )

        replica = capability_registry._replicas["replica-1"]
        assert len(replica.capabilities) == 2
        cap_types = [c.attributes["type"] for c in replica.capabilities]
        assert "embed" in cap_types
        assert "heavy" in cap_types


class TestCapabilityRegistryUnregister:
    """Tests for CapabilityRegistry.unregister()"""

    @pytest.mark.p0
    def test_unregister_replica(self, capability_registry):
        """Test unregistering a replica."""
        capability_registry.register(
            replica_id="to-remove",
            endpoint="localhost:50051",
            capabilities=[{"type": "test"}],
        )

        result = capability_registry.unregister("to-remove")

        assert result is True
        assert "to-remove" not in capability_registry._replicas

    @pytest.mark.p1
    def test_unregister_nonexistent(self, capability_registry):
        """Test unregistering a non-existent replica returns False."""
        result = capability_registry.unregister("nonexistent")
        assert result is False


class TestCapabilityRegistryLookup:
    """Tests for CapabilityRegistry.lookup()"""

    @pytest.fixture(autouse=True)
    def setup_replicas(self, capability_registry):
        """Set up test replicas."""
        capability_registry.register(
            replica_id="chat-replica",
            endpoint="localhost:50051",
            capabilities=[
                {"type": "chat", "model": "llama-7b"},
                {"type": "chat", "model": "llama-70b"},
            ],
        )
        capability_registry.register(
            replica_id="embed-replica",
            endpoint="localhost:50052",
            capabilities=[{"type": "embed"}],
        )
        capability_registry.register(
            replica_id="mixed-replica",
            endpoint="localhost:50053",
            capabilities=[
                {"type": "chat", "model": "llama-7b"},
                {"type": "heavy", "gpus": "2"},
            ],
        )

    @pytest.mark.p0
    def test_lookup_exact_match(self, capability_registry):
        """Test lookup with exact capability match."""
        result = capability_registry.lookup({"type": "chat", "model": "llama-70b"})

        assert result is not None
        assert result.replica_id == "chat-replica"

    @pytest.mark.p0
    def test_lookup_partial_match(self, capability_registry):
        """Test lookup with partial capability match (type only)."""
        result = capability_registry.lookup({"type": "embed"})

        assert result is not None
        assert result.replica_id == "embed-replica"

    @pytest.mark.p0
    def test_lookup_no_match(self, capability_registry):
        """Test lookup returns None when no match."""
        result = capability_registry.lookup({"type": "nonexistent"})
        assert result is None

    @pytest.mark.p0
    def test_lookup_exclude_replica(self, capability_registry):
        """Test lookup with excluded replica."""
        # First lookup should return chat-replica
        result1 = capability_registry.lookup({"type": "chat", "model": "llama-7b"})

        # Second lookup excluding that replica should return mixed-replica
        result2 = capability_registry.lookup(
            {"type": "chat", "model": "llama-7b"},
            exclude=["chat-replica"]
        )

        assert result1.replica_id == "chat-replica"
        assert result2.replica_id == "mixed-replica"

    @pytest.mark.p1
    def test_lookup_exclude_all_matching(self, capability_registry):
        """Test lookup returns None when all matching replicas excluded."""
        result = capability_registry.lookup(
            {"type": "embed"},
            exclude=["embed-replica"]
        )
        assert result is None


class TestCapabilityRegistryList:
    """Tests for CapabilityRegistry.list_all()"""

    @pytest.mark.p1
    def test_list_all_replicas(self, capability_registry):
        """Test listing all registered replicas."""
        capability_registry.register(
            replica_id="r1",
            endpoint="localhost:50051",
            capabilities=[{"type": "a"}],
        )
        capability_registry.register(
            replica_id="r2",
            endpoint="localhost:50052",
            capabilities=[{"type": "b"}],
        )

        replicas = capability_registry.list_all()

        assert len(replicas) == 2
        replica_ids = {r.replica_id for r in replicas}
        assert replica_ids == {"r1", "r2"}


class TestCapabilityRegistryGetRandomReplica:
    """Tests for CapabilityRegistry.get_random_replica()"""

    @pytest.mark.p1
    def test_get_random_replica(self, capability_registry):
        """Test random lookup returns a replica."""
        capability_registry.register(
            replica_id="r1",
            endpoint="localhost:50051",
            capabilities=[{"type": "a"}],
        )
        capability_registry.register(
            replica_id="r2",
            endpoint="localhost:50052",
            capabilities=[{"type": "b"}],
        )

        result = capability_registry.get_random_replica()

        assert result is not None
        assert result.replica_id in ["r1", "r2"]

    @pytest.mark.p1
    def test_get_random_replica_exclude(self, capability_registry):
        """Test random lookup with exclusion."""
        capability_registry.register(
            replica_id="r1",
            endpoint="localhost:50051",
            capabilities=[{"type": "a"}],
        )
        capability_registry.register(
            replica_id="r2",
            endpoint="localhost:50052",
            capabilities=[{"type": "b"}],
        )

        result = capability_registry.get_random_replica(exclude=["r1"])

        assert result is not None
        assert result.replica_id == "r2"

    @pytest.mark.p1
    def test_get_random_replica_empty(self, capability_registry):
        """Test random lookup on empty registry returns None."""
        result = capability_registry.get_random_replica()
        assert result is None


class TestReplicaInfo:
    """Tests for ReplicaInfo dataclass."""

    @pytest.mark.p1
    def test_replica_info_to_dict(self):
        """Test ReplicaInfo serialization to dict."""
        cap = Capability(type="chat")
        info = ReplicaInfo(
            replica_id="test",
            endpoint="localhost:8000",
            capabilities=[cap],
        )

        result = info.to_dict()

        assert result["replica_id"] == "test"
        assert result["endpoint"] == "localhost:8000"
        assert result["capabilities"] == [{"type": "chat"}]
        assert "registered_at" in result


class TestCapabilityClass:
    """Tests for Capability class in registry module."""

    @pytest.mark.p1
    def test_capability_matches(self):
        """Test Capability.matches() method."""
        cap = Capability(type="chat", model="demo")

        assert cap.matches({"type": "chat", "model": "demo"}) is True
        assert cap.matches({"type": "chat"}) is True
        assert cap.matches({"type": "embed"}) is False

    @pytest.mark.p1
    def test_capability_to_dict(self):
        """Test Capability.to_dict() method."""
        cap = Capability(type="test", value=123)
        result = cap.to_dict()

        assert result == {"type": "test", "value": 123}

    @pytest.mark.p1
    def test_capability_from_dict(self):
        """Test Capability.from_dict() method."""
        cap = Capability.from_dict({"type": "chat", "model": "llama"})

        assert cap.attributes["type"] == "chat"
        assert cap.attributes["model"] == "llama"
