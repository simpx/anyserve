"""
ObjectStore - File-based Object Storage for MVP.

Objects are stored as files in a shared directory (e.g., /tmp/anyserve-objects/).
This allows objects to be passed between Replicas on the same machine or via NFS.
"""

import os
import uuid
import json
import pickle
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Union
from pathlib import Path


@dataclass
class ObjRef:
    """
    Reference to an Object in the ObjectStore.

    ObjRef can be serialized and passed between Replicas.
    The receiving Replica can use the path to read the object.
    """
    path: str
    key: str
    size: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    content_type: str = "pickle"  # "pickle", "bytes", "json"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "key": self.key,
            "size": self.size,
            "created_at": self.created_at,
            "content_type": self.content_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ObjRef":
        return cls(**data)

    def to_string(self) -> str:
        """Serialize ObjRef to a string for passing in requests."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_string(cls, s: str) -> "ObjRef":
        """Deserialize ObjRef from a string."""
        return cls.from_dict(json.loads(s))

    def __str__(self):
        return self.path

    def __repr__(self):
        return f"ObjRef(key={self.key!r}, size={self.size}, type={self.content_type})"


class ObjectStore:
    """
    File-based Object Store.

    Stores objects as files in a shared directory.
    Supports pickle, bytes, and JSON content types.

    Usage:
        store = ObjectStore("/tmp/anyserve-objects")

        # Create object
        obj_ref = store.create({"key": "value"})

        # Read object
        data = store.get(obj_ref)

        # Delete object
        store.delete(obj_ref)

        # Create with specific key
        obj_ref = store.create(data, key="my-object")
    """

    def __init__(self, base_path: str = "/tmp/anyserve-objects"):
        """
        Initialize ObjectStore.

        Args:
            base_path: Directory to store objects
        """
        self.base_path = Path(base_path)
        self._ensure_directory()

    def _ensure_directory(self):
        """Create the storage directory if it doesn't exist."""
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _generate_key(self, data: Any = None) -> str:
        """Generate a unique key for an object."""
        # Use UUID + optional content hash for uniqueness
        unique_id = str(uuid.uuid4())[:12]

        if data is not None:
            try:
                # Try to create a content-based prefix
                content_bytes = pickle.dumps(data)
                content_hash = hashlib.md5(content_bytes).hexdigest()[:8]
                return f"obj-{content_hash}-{unique_id}"
            except Exception:
                pass

        return f"obj-{unique_id}"

    def _get_file_path(self, key: str, content_type: str = "pickle") -> Path:
        """Get the file path for an object key."""
        ext_map = {
            "pickle": ".pkl",
            "bytes": ".bin",
            "json": ".json",
        }
        ext = ext_map.get(content_type, ".bin")
        return self.base_path / f"{key}{ext}"

    def create(
        self,
        data: Any,
        key: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> ObjRef:
        """
        Create a new object in the store.

        Args:
            data: The data to store (any picklable object, bytes, or JSON-serializable)
            key: Optional key for the object. If None, a unique key is generated.
            content_type: Storage format ("pickle", "bytes", "json"). Auto-detected if None.

        Returns:
            ObjRef pointing to the created object
        """
        # Generate key if not provided
        if key is None:
            key = self._generate_key(data)

        # Auto-detect content type
        if content_type is None:
            if isinstance(data, bytes):
                content_type = "bytes"
            elif isinstance(data, (dict, list, str, int, float, bool, type(None))):
                content_type = "json"
            else:
                content_type = "pickle"

        # Get file path
        file_path = self._get_file_path(key, content_type)

        # Write data
        if content_type == "bytes":
            if not isinstance(data, bytes):
                data = pickle.dumps(data)
            file_path.write_bytes(data)
            size = len(data)
        elif content_type == "json":
            json_str = json.dumps(data)
            file_path.write_text(json_str)
            size = len(json_str)
        else:  # pickle
            content = pickle.dumps(data)
            file_path.write_bytes(content)
            size = len(content)

        # Create ObjRef
        obj_ref = ObjRef(
            path=str(file_path),
            key=key,
            size=size,
            content_type=content_type,
        )

        return obj_ref

    def get(self, obj_ref: Union[ObjRef, str, dict]) -> Any:
        """
        Read an object from the store.

        Args:
            obj_ref: ObjRef, path string, or dict representation

        Returns:
            The stored data
        """
        # Handle different input types
        if isinstance(obj_ref, str):
            # Could be a path or a JSON string
            if obj_ref.startswith("{"):
                obj_ref = ObjRef.from_string(obj_ref)
            else:
                # Assume it's a path
                path = Path(obj_ref)
                if not path.exists():
                    raise FileNotFoundError(f"Object not found: {obj_ref}")

                # Detect content type from extension
                if path.suffix == ".json":
                    return json.loads(path.read_text())
                elif path.suffix == ".pkl":
                    return pickle.loads(path.read_bytes())
                else:
                    return path.read_bytes()

        elif isinstance(obj_ref, dict):
            obj_ref = ObjRef.from_dict(obj_ref)

        # Read from file
        path = Path(obj_ref.path)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {obj_ref.path}")

        content_type = obj_ref.content_type

        if content_type == "bytes":
            return path.read_bytes()
        elif content_type == "json":
            return json.loads(path.read_text())
        else:  # pickle
            return pickle.loads(path.read_bytes())

    def delete(self, obj_ref: Union[ObjRef, str, dict]) -> bool:
        """
        Delete an object from the store.

        Args:
            obj_ref: ObjRef, path string, or dict representation

        Returns:
            True if deleted, False if not found
        """
        # Handle different input types
        if isinstance(obj_ref, str):
            if obj_ref.startswith("{"):
                obj_ref = ObjRef.from_string(obj_ref)
            else:
                path = Path(obj_ref)
        elif isinstance(obj_ref, dict):
            obj_ref = ObjRef.from_dict(obj_ref)

        if isinstance(obj_ref, ObjRef):
            path = Path(obj_ref.path)

        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, obj_ref: Union[ObjRef, str, dict]) -> bool:
        """Check if an object exists in the store."""
        if isinstance(obj_ref, str):
            if obj_ref.startswith("{"):
                obj_ref = ObjRef.from_string(obj_ref)
            else:
                return Path(obj_ref).exists()
        elif isinstance(obj_ref, dict):
            obj_ref = ObjRef.from_dict(obj_ref)

        return Path(obj_ref.path).exists()

    def list_objects(self) -> list:
        """List all objects in the store."""
        objects = []
        for file_path in self.base_path.iterdir():
            if file_path.is_file():
                key = file_path.stem
                content_type = {
                    ".pkl": "pickle",
                    ".bin": "bytes",
                    ".json": "json",
                }.get(file_path.suffix, "bytes")

                objects.append(ObjRef(
                    path=str(file_path),
                    key=key,
                    size=file_path.stat().st_size,
                    content_type=content_type,
                ))
        return objects

    def cleanup(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up old objects.

        Args:
            max_age_seconds: Delete objects older than this many seconds

        Returns:
            Number of objects deleted
        """
        import time
        now = time.time()
        deleted = 0

        for file_path in self.base_path.iterdir():
            if file_path.is_file():
                age = now - file_path.stat().st_mtime
                if age > max_age_seconds:
                    file_path.unlink()
                    deleted += 1

        return deleted

    def clear(self) -> int:
        """
        Delete all objects in the store.

        Returns:
            Number of objects deleted
        """
        deleted = 0
        for file_path in self.base_path.iterdir():
            if file_path.is_file():
                file_path.unlink()
                deleted += 1
        return deleted
