"""
Mock tests for llama.cpp serve functionality.

These tests use a mock engine to test the HTTP server and CLI flow
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


def test_handlers_app_creation():
    """Test FastAPI app creation."""
    from anyserve.builtins.llamacpp import LlamaCppConfig
    from anyserve.builtins.llamacpp.handlers import create_app

    cfg = LlamaCppConfig(model_path="/tmp/test.gguf", name="test-model")

    # Create mock engine
    mock_engine = Mock()
    mock_engine._model = True
    mock_engine.generate.return_value = "Generated text"

    app = create_app(cfg, mock_engine)

    # Test that app was created with correct routes
    routes = [r.path for r in app.routes]
    assert "/" in routes
    assert "/health" in routes
    assert "/v1/models" in routes
    assert "/v1/completions" in routes
    assert "/generate" in routes


def test_handlers_completion_endpoint():
    """Test completion endpoint with mock engine."""
    from fastapi.testclient import TestClient
    from anyserve.builtins.llamacpp import LlamaCppConfig
    from anyserve.builtins.llamacpp.handlers import create_app

    cfg = LlamaCppConfig(model_path="/tmp/test.gguf", name="test-model")

    # Create mock engine
    mock_engine = Mock()
    mock_engine._model = True
    mock_engine.generate.return_value = "This is a test response."

    app = create_app(cfg, mock_engine)
    client = TestClient(app)

    # Test health endpoint
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

    # Test models list
    response = client.get("/v1/models")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["id"] == "test-model"

    # Test completion (non-streaming)
    response = client.post("/v1/completions", json={
        "prompt": "Once upon a time",
        "max_tokens": 50
    })
    assert response.status_code == 200
    assert "choices" in response.json()
    assert response.json()["model"] == "test-model"

    # Verify engine was called
    mock_engine.generate.assert_called()


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


def test_cli_run_help():
    """Test run command help."""
    from click.testing import CliRunner
    from anyserve.cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ['run', '--help'])

    assert result.exit_code == 0
    assert '--port' in result.output
    assert '--workers' in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
