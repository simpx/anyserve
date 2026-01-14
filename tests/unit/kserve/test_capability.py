"""
Unit tests for Capability class.
"""

import pytest
from anyserve.kserve import Capability


class TestCapabilityInit:
    """Tests for Capability initialization."""

    @pytest.mark.p0
    def test_capability_init_single_attr(self):
        """Test Capability with single attribute."""
        cap = Capability(type="chat")

        assert cap.attributes["type"] == "chat"
        assert cap.get("type") == "chat"

    @pytest.mark.p0
    def test_capability_init_multiple_attrs(self):
        """Test Capability with multiple attributes."""
        cap = Capability(type="chat", model="llama-70b", version="v1")

        assert cap.get("type") == "chat"
        assert cap.get("model") == "llama-70b"
        assert cap.get("version") == "v1"

    @pytest.mark.p1
    def test_capability_get_default(self):
        """Test Capability.get() with default value."""
        cap = Capability(type="chat")

        assert cap.get("nonexistent") is None
        assert cap.get("nonexistent", "default") == "default"


class TestCapabilityMatches:
    """Tests for Capability.matches()"""

    @pytest.mark.p0
    def test_capability_matches_exact(self):
        """Test exact capability match."""
        cap = Capability(type="chat", model="llama-70b")

        assert cap.matches({"type": "chat", "model": "llama-70b"}) is True

    @pytest.mark.p0
    def test_capability_matches_partial(self):
        """Test partial capability match."""
        cap = Capability(type="chat", model="llama-70b", version="v1")

        # Query with subset of attributes should match
        assert cap.matches({"type": "chat"}) is True
        assert cap.matches({"type": "chat", "model": "llama-70b"}) is True

    @pytest.mark.p0
    def test_capability_no_match_wrong_value(self):
        """Test capability doesn't match with wrong value."""
        cap = Capability(type="chat", model="llama-70b")

        assert cap.matches({"type": "chat", "model": "llama-7b"}) is False

    @pytest.mark.p0
    def test_capability_no_match_missing_attr(self):
        """Test capability doesn't match when query has extra attributes."""
        cap = Capability(type="chat")

        # Capability doesn't have "model" attribute
        assert cap.matches({"type": "chat", "model": "demo"}) is False

    @pytest.mark.p1
    def test_capability_matches_empty_query(self):
        """Test empty query matches any capability."""
        cap = Capability(type="chat", model="demo")

        assert cap.matches({}) is True


class TestCapabilityToDict:
    """Tests for Capability.to_dict()"""

    @pytest.mark.p1
    def test_capability_to_dict(self):
        """Test Capability serialization to dict."""
        cap = Capability(type="chat", model="demo", gpus=2)

        result = cap.to_dict()

        assert result == {"type": "chat", "model": "demo", "gpus": 2}

    @pytest.mark.p1
    def test_capability_to_dict_returns_copy(self):
        """Test to_dict returns a copy, not the original."""
        cap = Capability(type="chat")
        result = cap.to_dict()

        result["type"] = "modified"

        assert cap.get("type") == "chat"  # Original unchanged


class TestCapabilityRepr:
    """Tests for Capability string representation."""

    @pytest.mark.p2
    def test_capability_repr(self):
        """Test Capability __repr__ is informative."""
        cap = Capability(type="chat", model="demo")
        repr_str = repr(cap)

        assert "Capability" in repr_str
        assert "chat" in repr_str
        assert "demo" in repr_str
