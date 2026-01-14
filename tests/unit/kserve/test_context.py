"""
Unit tests for Context class.
"""

import pytest
from anyserve.kserve import Context, Capability


class TestContextObjects:
    """Tests for Context.objects property."""

    @pytest.mark.p0
    def test_context_objects_access(self, object_store):
        """Test accessing ObjectStore through context."""
        ctx = Context(objects=object_store)

        # Should be able to access objects
        obj_ref = ctx.objects.create({"test": "data"})
        assert obj_ref is not None

        data = ctx.objects.get(obj_ref)
        assert data == {"test": "data"}

    @pytest.mark.p1
    def test_context_objects_not_configured(self):
        """Test accessing objects when not configured raises error."""
        ctx = Context(objects=None)

        with pytest.raises(RuntimeError, match="ObjectStore not available"):
            _ = ctx.objects


class TestContextCall:
    """Tests for Context.call() method."""

    @pytest.mark.p1
    def test_context_call_not_configured(self):
        """Test calling when not configured raises error."""
        ctx = Context(call_func=None)

        with pytest.raises(RuntimeError, match="Cross-Replica call not available"):
            ctx.call({"type": "chat"}, {"text": "hello"})

    @pytest.mark.p0
    def test_context_call_invokes_function(self):
        """Test call invokes the provided function."""
        call_log = []

        def mock_call(capability, inputs, **kwargs):
            call_log.append((capability, inputs, kwargs))
            return {"result": "success"}

        ctx = Context(call_func=mock_call)

        result = ctx.call({"type": "embed"}, {"text": "hello"}, timeout=30)

        assert result == {"result": "success"}
        assert len(call_log) == 1
        assert call_log[0][0] == {"type": "embed"}
        assert call_log[0][1] == {"text": "hello"}
        assert call_log[0][2] == {"timeout": 30}


class TestContextAttributes:
    """Tests for Context attributes."""

    @pytest.mark.p1
    def test_context_replica_id(self):
        """Test Context stores replica_id."""
        ctx = Context(replica_id="replica-123")
        assert ctx.replica_id == "replica-123"

    @pytest.mark.p1
    def test_context_capability(self):
        """Test Context stores matched capability."""
        cap = Capability(type="chat", model="demo")
        ctx = Context(capability=cap)

        assert ctx.capability is cap
        assert ctx.capability.get("type") == "chat"

    @pytest.mark.p1
    def test_context_full_init(self, object_store):
        """Test Context with all parameters."""
        cap = Capability(type="test")

        def mock_call(c, i, **k):
            return {}

        ctx = Context(
            objects=object_store,
            call_func=mock_call,
            replica_id="full-test",
            capability=cap,
        )

        assert ctx.objects is object_store
        assert ctx.replica_id == "full-test"
        assert ctx.capability is cap
