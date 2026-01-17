"""
Mock tests for llama.cpp serve functionality.

These tests use a mock engine to test the AnyServe worker and CLI flow
without requiring a real GGUF model.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))


class MockLlama:
    """Mock Llama class for testing."""

    def __init__(self, *args, **kwargs):
        self.model_path = kwargs.get('model_path', '')

    def __call__(self, prompt, **kwargs):
        """Mock generation."""
        if kwargs.get('stream', False):
            return self._stream_generate(prompt, **kwargs)
        return {
            "choices": [{"text": f"Generated response for: {prompt[:50]}..."}]
        }

    def _stream_generate(self, prompt, **kwargs):
        """Mock streaming generation."""
        tokens = ["Hello", " ", "world", "!"]
        for token in tokens:
            yield {"choices": [{"text": token}]}


def test_config_creation():
    """Test LlamaCppConfig creation and validation."""
    from anyserve.builtins.llamacpp import LlamaCppConfig

    # Test basic creation
    cfg = LlamaCppConfig(
        model_path="/tmp/test.gguf",
        name="test-model",
        port=8000
    )
    assert cfg.model_path == "/tmp/test.gguf"
    assert cfg.name == "test-model"
    assert cfg.port == 8000
    assert cfg.n_ctx == 2048  # default

    # Test validation - missing model_path
    cfg_empty = LlamaCppConfig(model_path="")
    with pytest.raises(ValueError, match="model_path is required"):
        cfg_empty.validate()


def test_config_from_yaml(tmp_path):
    """Test loading config from YAML file."""
    from anyserve.builtins.llamacpp import LlamaCppConfig

    # Create test YAML file
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
model_path: /models/test.gguf
name: test-model
n_ctx: 4096
port: 9000
temperature: 0.8
""")

    cfg = LlamaCppConfig.from_yaml(str(config_file))
    assert cfg.model_path == "/models/test.gguf"
    assert cfg.name == "test-model"
    assert cfg.n_ctx == 4096
    assert cfg.port == 9000
    assert cfg.temperature == 0.8


@patch('anyserve.builtins.llamacpp.engine.Llama', MockLlama)
def test_engine_generate():
    """Test LlamaCppEngine with mock Llama."""
    from anyserve.builtins.llamacpp import LlamaCppConfig, LlamaCppEngine

    cfg = LlamaCppConfig(model_path="/tmp/test.gguf", name="test")
    engine = LlamaCppEngine(cfg)

    # Mock the model loading
    engine._model = MockLlama(model_path=cfg.model_path)

    # Test generation
    result = engine.generate("Hello, world!")
    assert "Generated response" in result


@patch('anyserve.builtins.llamacpp.engine.Llama', MockLlama)
def test_engine_stream():
    """Test LlamaCppEngine streaming with mock Llama."""
    from anyserve.builtins.llamacpp import LlamaCppConfig, LlamaCppEngine

    cfg = LlamaCppConfig(model_path="/tmp/test.gguf", name="test")
    engine = LlamaCppEngine(cfg)

    # Mock the model loading
    engine._model = MockLlama(model_path=cfg.model_path)

    # Test streaming
    tokens = list(engine.generate_stream("Hello"))
    assert len(tokens) == 4
    assert "".join(tokens) == "Hello world!"


def test_anyserve_app_creation():
    """Test AnyServe app with llamacpp capabilities."""
    from anyserve.builtins.llamacpp.app import app

    # Check that app is created
    assert app is not None

    # Check that capabilities are registered
    capabilities = app.get_capabilities()
    assert len(capabilities) >= 2  # generate and generate_stream

    # Check capability types
    cap_types = [cap.get("type") for cap in capabilities]
    assert "generate" in cap_types
    assert "generate_stream" in cap_types


def test_anyserve_app_find_handler():
    """Test finding handlers by capability."""
    from anyserve.builtins.llamacpp.app import app

    # Find generate handler
    result = app.find_handler({"type": "generate"})
    assert result is not None
    handler, uses_context, capability = result
    assert callable(handler)
    assert uses_context is True

    # Find stream handler
    result = app.find_stream_handler({"type": "generate_stream"})
    assert result is not None
    handler, uses_context, capability = result
    assert callable(handler)


def test_openai_server_app_creation():
    """Test OpenAI server app creation."""
    from anyserve.builtins.llamacpp.openai_compat import create_app

    app = create_app("localhost:8000")

    # Test that app was created with correct routes
    routes = [r.path for r in app.routes]
    assert "/" in routes
    assert "/health" in routes
    assert "/v1/models" in routes
    assert "/v1/completions" in routes
    assert "/v1/chat/completions" in routes


def test_openai_server_endpoints():
    """Test OpenAI server endpoints with mock client."""
    from fastapi.testclient import TestClient
    from anyserve.builtins.llamacpp.openai_compat import create_app
    from unittest.mock import patch

    app = create_app("localhost:8000")
    client = TestClient(app)

    # Test root endpoint
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Test models list (will use mock)
    with patch('anyserve.builtins.llamacpp.openai_compat.server.KServeClient') as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.get_model_info.return_value = {"model_name": "test-model"}

        response = client.get("/v1/models")
        assert response.status_code == 200
        assert "data" in response.json()


def test_cli_serve_help():
    """Test serve command help."""
    from click.testing import CliRunner
    from anyserve.cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ['serve', '--help'])

    assert result.exit_code == 0
    assert 'MODEL_PATH' in result.output
    assert '--name' in result.output
    assert '--port' in result.output
    assert '--n-ctx' in result.output
    assert '--workers' in result.output
    assert '--openai-port' in result.output
    assert '--openai-host' in result.output


def test_cli_run_help():
    """Test run command help."""
    from click.testing import CliRunner
    from anyserve.cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ['run', '--help'])

    assert result.exit_code == 0
    assert '--port' in result.output
    assert '--workers' in result.output


def test_kserve_client_creation():
    """Test KServe client creation."""
    from anyserve.builtins.llamacpp.openai_compat import KServeClient

    client = KServeClient("localhost:8000")
    assert client.endpoint == "localhost:8000"
    assert client._channel is None  # Not connected yet


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
