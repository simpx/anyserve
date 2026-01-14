"""
AnyServe API Server - MVP Demo Version

This module provides a simple API Server for routing requests
based on Capability key-value pairs.
"""

from .registry import CapabilityRegistry, ReplicaInfo, Capability
from .router import create_app

__all__ = [
    "CapabilityRegistry",
    "ReplicaInfo",
    "Capability",
    "create_app",
]
