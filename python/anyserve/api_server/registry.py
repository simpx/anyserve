"""
Capability Registry - Manages Replica registration and lookup.

The registry maintains a mapping from Capability (key-value pairs)
to Replica endpoints.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import threading
import uuid


@dataclass
class Capability:
    """
    Represents a Capability with key-value attributes.

    Examples:
        Capability(type="chat", model="llama-70b")
        Capability(type="embed")
        Capability(type="heavy", gpus=2)
    """
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, **kwargs):
        self.attributes = kwargs

    def matches(self, query: Dict[str, Any]) -> bool:
        """
        Check if this capability matches a query.

        A capability matches if all query keys exist in the capability
        with the same values.
        """
        for key, value in query.items():
            if key not in self.attributes:
                return False
            if self.attributes[key] != value:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return self.attributes.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """Get an attribute value by key."""
        return self.attributes.get(key, default)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Capability":
        return cls(**data)

    def __hash__(self):
        return hash(tuple(sorted(self.attributes.items())))

    def __eq__(self, other):
        if not isinstance(other, Capability):
            return False
        return self.attributes == other.attributes

    def __repr__(self):
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.attributes.items())
        return f"Capability({attrs})"


@dataclass
class ReplicaInfo:
    """Information about a registered Replica."""
    replica_id: str
    endpoint: str  # e.g., "localhost:50051"
    capabilities: List[Capability]
    registered_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "replica_id": self.replica_id,
            "endpoint": self.endpoint,
            "capabilities": [cap.to_dict() for cap in self.capabilities],
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }


class CapabilityRegistry:
    """
    Thread-safe registry for Replica capabilities.

    The registry maintains:
    - A mapping from replica_id to ReplicaInfo
    - An index from Capability to list of Replicas
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._replicas: Dict[str, ReplicaInfo] = {}  # replica_id -> ReplicaInfo
        self._capability_index: Dict[Capability, List[str]] = {}  # Capability -> [replica_id]

    def register(
        self,
        replica_id: str,
        endpoint: str,
        capabilities: List[Dict[str, Any]]
    ) -> bool:
        """
        Register a Replica with its capabilities.

        Args:
            replica_id: Unique identifier for the replica
            endpoint: gRPC endpoint (e.g., "localhost:50051")
            capabilities: List of capability dicts

        Returns:
            True if registration was successful
        """
        with self._lock:
            # Convert capability dicts to Capability objects
            caps = [Capability.from_dict(c) for c in capabilities]

            # If replica already exists, unregister first
            if replica_id in self._replicas:
                self._unregister_internal(replica_id)

            # Create ReplicaInfo
            info = ReplicaInfo(
                replica_id=replica_id,
                endpoint=endpoint,
                capabilities=caps,
            )

            # Register
            self._replicas[replica_id] = info

            # Update capability index
            for cap in caps:
                if cap not in self._capability_index:
                    self._capability_index[cap] = []
                self._capability_index[cap].append(replica_id)

            return True

    def unregister(self, replica_id: str) -> bool:
        """
        Unregister a Replica.

        Args:
            replica_id: The replica to unregister

        Returns:
            True if the replica was found and unregistered
        """
        with self._lock:
            return self._unregister_internal(replica_id)

    def _unregister_internal(self, replica_id: str) -> bool:
        """Internal unregister (must hold lock)."""
        if replica_id not in self._replicas:
            return False

        info = self._replicas[replica_id]

        # Remove from capability index
        for cap in info.capabilities:
            if cap in self._capability_index:
                if replica_id in self._capability_index[cap]:
                    self._capability_index[cap].remove(replica_id)
                if not self._capability_index[cap]:
                    del self._capability_index[cap]

        # Remove replica
        del self._replicas[replica_id]
        return True

    def lookup(
        self,
        capability_query: Dict[str, Any],
        exclude: Optional[List[str]] = None
    ) -> Optional[ReplicaInfo]:
        """
        Find a Replica that matches the capability query.

        Args:
            capability_query: Key-value pairs to match (e.g., {"type": "chat"})
            exclude: List of replica_ids to exclude (for delegation)

        Returns:
            ReplicaInfo if found, None otherwise
        """
        with self._lock:
            exclude = exclude or []

            # Search through all replicas
            for replica_id, info in self._replicas.items():
                if replica_id in exclude:
                    continue

                # Check if any capability matches
                for cap in info.capabilities:
                    if cap.matches(capability_query):
                        return info

            return None

    def lookup_all(
        self,
        capability_query: Dict[str, Any],
        exclude: Optional[List[str]] = None
    ) -> List[ReplicaInfo]:
        """
        Find all Replicas that match the capability query.

        Args:
            capability_query: Key-value pairs to match
            exclude: List of replica_ids to exclude

        Returns:
            List of matching ReplicaInfo objects
        """
        with self._lock:
            exclude = exclude or []
            results = []

            for replica_id, info in self._replicas.items():
                if replica_id in exclude:
                    continue

                for cap in info.capabilities:
                    if cap.matches(capability_query):
                        results.append(info)
                        break  # Only add once per replica

            return results

    def get_replica(self, replica_id: str) -> Optional[ReplicaInfo]:
        """Get a specific Replica by ID."""
        with self._lock:
            return self._replicas.get(replica_id)

    def list_all(self) -> List[ReplicaInfo]:
        """List all registered Replicas."""
        with self._lock:
            return list(self._replicas.values())

    def update_heartbeat(self, replica_id: str) -> bool:
        """Update the heartbeat timestamp for a Replica."""
        with self._lock:
            if replica_id in self._replicas:
                self._replicas[replica_id].last_heartbeat = datetime.now()
                return True
            return False

    def get_random_replica(self, exclude: Optional[List[str]] = None) -> Optional[ReplicaInfo]:
        """Get a random Replica (for fallback routing)."""
        import random
        with self._lock:
            exclude = exclude or []
            available = [
                info for rid, info in self._replicas.items()
                if rid not in exclude
            ]
            if available:
                return random.choice(available)
            return None
