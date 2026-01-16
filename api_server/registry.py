"""
Capability Registry - Manages Replica registration and lookup.

This is a simplified MVP implementation focused on:
- Key-value based capability matching
- SSE-based keepalive (connection-based cleanup)
- Simple load balancing (random selection)
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import threading
import random


@dataclass
class ReplicaInfo:
    """Information about a registered Replica."""
    replica_id: str
    endpoint: str  # e.g., "localhost:50051"
    capabilities: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "replica_id": self.replica_id,
            "endpoint": self.endpoint,
            "capabilities": self.capabilities,
        }


class CapabilityRegistry:
    """
    Thread-safe registry for Replica capabilities.

    Matching rules:
    - Query params construct query conditions
    - Query conditions must be a subset of Replica capabilities to match
    - Multiple matches: random selection (simple load balancing)
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._replicas: Dict[str, ReplicaInfo] = {}  # replica_id -> ReplicaInfo

    def register(
        self,
        replica_id: str,
        endpoint: str,
        capabilities: List[Dict[str, Any]]
    ) -> None:
        """
        Register a Replica with its capabilities.

        Args:
            replica_id: Unique identifier for the replica
            endpoint: gRPC endpoint (e.g., "localhost:50051")
            capabilities: List of capability dicts (e.g., [{"model": "qwen2"}])
        """
        with self._lock:
            # If replica already exists, update it
            self._replicas[replica_id] = ReplicaInfo(
                replica_id=replica_id,
                endpoint=endpoint,
                capabilities=capabilities,
            )

    def unregister(self, replica_id: str) -> None:
        """
        Unregister a Replica.

        Args:
            replica_id: The replica to unregister
        """
        with self._lock:
            if replica_id in self._replicas:
                del self._replicas[replica_id]

    def lookup(self, query: Dict[str, Any]) -> Optional[ReplicaInfo]:
        """
        Find a Replica that matches the capability query.

        Query must be a subset of at least one capability of the replica.

        Args:
            query: Key-value pairs to match (e.g., {"model": "qwen2"})

        Returns:
            ReplicaInfo if found, None otherwise
        """
        with self._lock:
            matches = []

            for info in self._replicas.values():
                if self._matches_any_capability(info.capabilities, query):
                    matches.append(info)

            if matches:
                # Simple load balancing: random selection
                return random.choice(matches)
            return None

    def _matches_any_capability(
        self,
        capabilities: List[Dict[str, Any]],
        query: Dict[str, Any]
    ) -> bool:
        """Check if query is a subset of any capability."""
        for cap in capabilities:
            if self._is_subset(query, cap):
                return True
        return False

    def _is_subset(self, query: Dict[str, Any], capability: Dict[str, Any]) -> bool:
        """Check if query is a subset of capability."""
        for key, value in query.items():
            if key not in capability:
                return False
            if capability[key] != value:
                return False
        return True

    def list_all(self) -> List[ReplicaInfo]:
        """List all registered Replicas."""
        with self._lock:
            return list(self._replicas.values())
