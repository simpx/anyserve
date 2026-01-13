"""
Unit tests for ObjectStore.
"""

import os
import time
import pytest
from pathlib import Path


class TestObjectStoreCreate:
    """Tests for ObjectStore.create()"""

    @pytest.mark.p0
    def test_create_object_pickle(self, object_store):
        """Test creating an object with pickle format (explicit or for complex types)."""
        # Use explicit pickle content_type for dict
        data = {"key": "value", "list": [1, 2, 3]}
        obj_ref = object_store.create(data, content_type="pickle")

        assert obj_ref is not None
        assert obj_ref.path.endswith(".pkl")
        assert obj_ref.content_type == "pickle"
        assert obj_ref.size > 0
        assert Path(obj_ref.path).exists()

    @pytest.mark.p0
    def test_create_object_json(self, object_store):
        """Test creating an object with JSON format (auto-detected for dicts)."""
        data = {"simple": "dict"}
        obj_ref = object_store.create(data, content_type="json")

        assert obj_ref is not None
        assert obj_ref.path.endswith(".json")
        assert obj_ref.content_type == "json"
        assert Path(obj_ref.path).exists()

    @pytest.mark.p0
    def test_create_object_bytes(self, object_store):
        """Test creating an object with bytes format."""
        data = b"raw binary data"
        obj_ref = object_store.create(data)

        assert obj_ref is not None
        assert obj_ref.path.endswith(".bin")
        assert obj_ref.content_type == "bytes"
        assert obj_ref.size == len(data)

    @pytest.mark.p1
    def test_create_object_custom_key(self, object_store):
        """Test creating an object with a custom key."""
        data = {"data": "test"}
        obj_ref = object_store.create(data, key="my-custom-key")

        assert obj_ref is not None
        assert obj_ref.key == "my-custom-key"
        assert "my-custom-key" in obj_ref.path

    @pytest.mark.p1
    def test_create_object_auto_detect_json(self, object_store):
        """Test that simple types auto-detect to JSON."""
        for data in [{"dict": "value"}, [1, 2, 3], "string", 123, True, None]:
            obj_ref = object_store.create(data)
            assert obj_ref.content_type == "json"


class TestObjectStoreGet:
    """Tests for ObjectStore.get()"""

    @pytest.mark.p0
    def test_get_object_by_ref(self, object_store):
        """Test reading an object by ObjRef."""
        original_data = {"key": "value", "nested": {"a": 1}}
        obj_ref = object_store.create(original_data)

        retrieved_data = object_store.get(obj_ref)

        assert retrieved_data == original_data

    @pytest.mark.p0
    def test_get_object_by_path_string(self, object_store):
        """Test reading an object by path string."""
        original_data = b"binary content"
        obj_ref = object_store.create(original_data)

        retrieved_data = object_store.get(obj_ref.path)

        assert retrieved_data == original_data

    @pytest.mark.p0
    def test_get_object_by_dict(self, object_store):
        """Test reading an object by dict representation."""
        original_data = {"test": "data"}
        obj_ref = object_store.create(original_data, content_type="json")

        retrieved_data = object_store.get(obj_ref.to_dict())

        assert retrieved_data == original_data

    @pytest.mark.p0
    def test_get_object_by_json_string(self, object_store):
        """Test reading an object by JSON string representation."""
        original_data = [1, 2, 3, 4, 5]
        obj_ref = object_store.create(original_data)

        retrieved_data = object_store.get(obj_ref.to_string())

        assert retrieved_data == original_data

    @pytest.mark.p1
    def test_get_nonexistent_object(self, object_store):
        """Test reading a non-existent object raises error."""
        with pytest.raises(FileNotFoundError):
            object_store.get("/nonexistent/path/obj.pkl")


class TestObjectStoreDelete:
    """Tests for ObjectStore.delete()"""

    @pytest.mark.p1
    def test_delete_object(self, object_store):
        """Test deleting an object."""
        obj_ref = object_store.create({"data": "to delete"})
        assert Path(obj_ref.path).exists()

        result = object_store.delete(obj_ref)

        assert result is True
        assert not Path(obj_ref.path).exists()

    @pytest.mark.p1
    def test_delete_nonexistent_object(self, object_store):
        """Test deleting a non-existent object returns False."""
        result = object_store.delete("/nonexistent/path.pkl")
        assert result is False


class TestObjectStoreOperations:
    """Tests for other ObjectStore operations."""

    @pytest.mark.p1
    def test_exists_true(self, object_store):
        """Test exists returns True for existing object."""
        obj_ref = object_store.create({"data": "exists"})
        assert object_store.exists(obj_ref) is True

    @pytest.mark.p1
    def test_exists_false(self, object_store):
        """Test exists returns False for non-existing object."""
        assert object_store.exists("/nonexistent/path.pkl") is False

    @pytest.mark.p2
    def test_list_objects(self, object_store):
        """Test listing all objects in the store."""
        # Create several objects
        obj_refs = [
            object_store.create({"data": i}) for i in range(3)
        ]

        listed = object_store.list_objects()

        assert len(listed) == 3
        listed_keys = {obj.key for obj in listed}
        expected_keys = {obj.key for obj in obj_refs}
        assert listed_keys == expected_keys

    @pytest.mark.p2
    def test_cleanup_old_objects(self, object_store):
        """Test cleaning up old objects."""
        # Create object
        obj_ref = object_store.create({"old": "data"})

        # Cleanup with 0 seconds max age (all objects are "old")
        deleted_count = object_store.cleanup(max_age_seconds=0)

        assert deleted_count == 1
        assert not Path(obj_ref.path).exists()

    @pytest.mark.p2
    def test_clear_all_objects(self, object_store):
        """Test clearing all objects from the store."""
        # Create several objects
        for i in range(5):
            object_store.create({"data": i})

        deleted_count = object_store.clear()

        assert deleted_count == 5
        assert len(object_store.list_objects()) == 0


class TestObjectStoreEdgeCases:
    """Edge case tests for ObjectStore."""

    @pytest.mark.p1
    def test_create_large_object(self, object_store):
        """Test creating a large object."""
        large_data = {"array": list(range(100000))}
        obj_ref = object_store.create(large_data)

        retrieved = object_store.get(obj_ref)
        assert retrieved == large_data

    @pytest.mark.p1
    def test_create_object_with_special_characters(self, object_store):
        """Test creating object with special characters in data."""
        data = {"special": "中文字符 émoji 🚀 special<>chars&"}
        obj_ref = object_store.create(data)

        retrieved = object_store.get(obj_ref)
        assert retrieved == data

    @pytest.mark.p2
    def test_concurrent_creates(self, object_store):
        """Test creating multiple objects doesn't cause conflicts."""
        import concurrent.futures

        def create_obj(i):
            return object_store.create({"index": i})

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_obj, i) for i in range(20)]
            results = [f.result() for f in futures]

        assert len(results) == 20
        assert len(set(r.key for r in results)) == 20  # All unique keys
