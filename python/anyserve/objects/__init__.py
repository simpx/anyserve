"""
AnyServe Object System - MVP Version

This module provides a simplified Object System based on shared filesystem.
Objects are stored as files in a shared directory.
"""

from .store import ObjectStore, ObjRef

__all__ = [
    "ObjectStore",
    "ObjRef",
]
