"""
Pytest configuration and fixtures for AnyServe tests.
"""

import os
import sys
import tempfile
import shutil
import pytest

# Add python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp = tempfile.mkdtemp(prefix="anyserve-test-")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def object_store(temp_dir):
    """Create an ObjectStore instance with a temp directory."""
    from anyserve.objects import ObjectStore
    return ObjectStore(temp_dir)


@pytest.fixture
def capability_registry():
    """Create a fresh CapabilityRegistry instance."""
    from anyserve.api_server.registry import CapabilityRegistry
    return CapabilityRegistry()


@pytest.fixture
def anyserve_app():
    """Create a fresh AnyServe app instance."""
    from anyserve import AnyServe
    return AnyServe()


@pytest.fixture
def sample_replica_info():
    """Sample replica registration data."""
    return {
        "replica_id": "test-replica-1",
        "endpoint": "localhost:50051",
        "capabilities": [
            {"type": "chat", "model": "demo"},
            {"type": "embed"},
        ]
    }


@pytest.fixture
def sample_infer_request():
    """Sample inference request data."""
    return {
        "model_name": "chat",
        "inputs": [
            {
                "name": "text",
                "datatype": "BYTES",
                "shape": [1],
                "contents": {
                    "bytes_contents": ["Hello World"]
                }
            }
        ]
    }


# Pytest markers
def pytest_configure(config):
    config.addinivalue_line("markers", "p0: Priority 0 (critical) tests")
    config.addinivalue_line("markers", "p1: Priority 1 (high) tests")
    config.addinivalue_line("markers", "p2: Priority 2 (medium) tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "integration: Integration tests")
