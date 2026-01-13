"""
Unit tests for ObjRef.
"""

import json
import pytest
from anyserve.objects import ObjRef


class TestObjRefSerialization:
    """Tests for ObjRef serialization."""

    @pytest.mark.p0
    def test_obj_ref_to_dict(self):
        """Test ObjRef serialization to dict."""
        obj_ref = ObjRef(
            path="/tmp/test/obj-123.pkl",
            key="obj-123",
            size=1024,
            content_type="pickle",
        )

        result = obj_ref.to_dict()

        assert result["path"] == "/tmp/test/obj-123.pkl"
        assert result["key"] == "obj-123"
        assert result["size"] == 1024
        assert result["content_type"] == "pickle"
        assert "created_at" in result

    @pytest.mark.p0
    def test_obj_ref_from_dict(self):
        """Test ObjRef deserialization from dict."""
        data = {
            "path": "/tmp/test/obj-456.json",
            "key": "obj-456",
            "size": 512,
            "content_type": "json",
            "created_at": "2024-01-01T00:00:00",
        }

        obj_ref = ObjRef.from_dict(data)

        assert obj_ref.path == "/tmp/test/obj-456.json"
        assert obj_ref.key == "obj-456"
        assert obj_ref.size == 512
        assert obj_ref.content_type == "json"
        assert obj_ref.created_at == "2024-01-01T00:00:00"

    @pytest.mark.p0
    def test_obj_ref_to_string(self):
        """Test ObjRef serialization to JSON string."""
        obj_ref = ObjRef(
            path="/tmp/obj.bin",
            key="obj",
            size=100,
            content_type="bytes",
        )

        result = obj_ref.to_string()

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["path"] == "/tmp/obj.bin"
        assert parsed["key"] == "obj"

    @pytest.mark.p0
    def test_obj_ref_from_string(self):
        """Test ObjRef deserialization from JSON string."""
        json_str = json.dumps({
            "path": "/tmp/obj.pkl",
            "key": "obj",
            "size": 200,
            "content_type": "pickle",
            "created_at": "2024-01-01T00:00:00",
        })

        obj_ref = ObjRef.from_string(json_str)

        assert obj_ref.path == "/tmp/obj.pkl"
        assert obj_ref.key == "obj"
        assert obj_ref.size == 200

    @pytest.mark.p1
    def test_obj_ref_roundtrip_dict(self):
        """Test ObjRef dict serialization roundtrip."""
        original = ObjRef(
            path="/tmp/test.pkl",
            key="test",
            size=999,
            content_type="pickle",
        )

        restored = ObjRef.from_dict(original.to_dict())

        assert restored.path == original.path
        assert restored.key == original.key
        assert restored.size == original.size
        assert restored.content_type == original.content_type

    @pytest.mark.p1
    def test_obj_ref_roundtrip_string(self):
        """Test ObjRef string serialization roundtrip."""
        original = ObjRef(
            path="/tmp/test.json",
            key="test",
            size=500,
            content_type="json",
        )

        restored = ObjRef.from_string(original.to_string())

        assert restored.path == original.path
        assert restored.key == original.key


class TestObjRefStr:
    """Tests for ObjRef string representations."""

    @pytest.mark.p1
    def test_obj_ref_str(self):
        """Test ObjRef __str__ returns path."""
        obj_ref = ObjRef(path="/tmp/obj.pkl", key="obj")
        assert str(obj_ref) == "/tmp/obj.pkl"

    @pytest.mark.p1
    def test_obj_ref_repr(self):
        """Test ObjRef __repr__ is informative."""
        obj_ref = ObjRef(
            path="/tmp/obj.pkl",
            key="test-key",
            size=1000,
            content_type="pickle",
        )
        repr_str = repr(obj_ref)

        assert "test-key" in repr_str
        assert "1000" in repr_str
        assert "pickle" in repr_str
