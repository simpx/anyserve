"""
Unit tests for AnyServe app class and decorators.
"""

import pytest
from anyserve import AnyServe, ModelInferRequest, ModelInferResponse, Context


class TestCapabilityDecorator:
    """Tests for @app.capability decorator."""

    @pytest.mark.p0
    def test_capability_decorator_registers_handler(self):
        """Test @app.capability registers the handler."""
        app = AnyServe()

        @app.capability(type="chat", model="demo")
        def chat_handler(request, context):
            return ModelInferResponse(model_name="chat")

        assert len(app._capability_handlers) == 1
        cap, handler, uses_context = app._capability_handlers[0]
        assert cap.get("type") == "chat"
        assert cap.get("model") == "demo"
        assert handler is chat_handler

    @pytest.mark.p0
    def test_capability_decorator_detects_context(self):
        """Test decorator correctly detects context parameter."""
        app = AnyServe()

        @app.capability(type="with_context")
        def with_context_handler(request, context):
            pass

        @app.capability(type="without_context")
        def without_context_handler(request):
            pass

        # Find handlers
        _, _, uses_ctx1 = app._capability_handlers[0]
        _, _, uses_ctx2 = app._capability_handlers[1]

        assert uses_ctx1 is True
        assert uses_ctx2 is False

    @pytest.mark.p0
    def test_capability_decorator_multiple_handlers(self):
        """Test registering multiple capability handlers."""
        app = AnyServe()

        @app.capability(type="chat")
        def chat_handler(request, context):
            pass

        @app.capability(type="embed")
        def embed_handler(request, context):
            pass

        @app.capability(type="heavy", gpus=2)
        def heavy_handler(request, context):
            pass

        assert len(app._capability_handlers) == 3

    @pytest.mark.p1
    def test_capability_decorator_preserves_function(self):
        """Test decorator returns the original function."""
        app = AnyServe()

        @app.capability(type="test")
        def original_func(request, context):
            return "original"

        # The decorated function should be the same
        assert original_func.__name__ == "original_func"


class TestModelDecorator:
    """Tests for @app.model decorator (backward compatibility)."""

    @pytest.mark.p1
    def test_model_decorator_registers_handler(self):
        """Test @app.model registers the handler."""
        app = AnyServe()

        @app.model("my_model")
        def model_handler(request):
            return ModelInferResponse(model_name="my_model")

        assert ("my_model", None) in app._local_registry
        assert app._local_registry[("my_model", None)] is model_handler

    @pytest.mark.p1
    def test_model_decorator_with_version(self):
        """Test @app.model with version."""
        app = AnyServe()

        @app.model("classifier", version="v2")
        def classifier_v2(request):
            return ModelInferResponse(model_name="classifier", model_version="v2")

        assert ("classifier", "v2") in app._local_registry


class TestGetCapabilities:
    """Tests for AnyServe.get_capabilities()"""

    @pytest.mark.p0
    def test_get_capabilities_empty(self):
        """Test get_capabilities on empty app."""
        app = AnyServe()
        caps = app.get_capabilities()
        assert caps == []

    @pytest.mark.p0
    def test_get_capabilities_returns_dicts(self):
        """Test get_capabilities returns list of dicts."""
        app = AnyServe()

        @app.capability(type="chat", model="demo")
        def handler1(request, context):
            pass

        @app.capability(type="embed")
        def handler2(request, context):
            pass

        caps = app.get_capabilities()

        assert len(caps) == 2
        assert {"type": "chat", "model": "demo"} in caps
        assert {"type": "embed"} in caps


class TestFindHandler:
    """Tests for AnyServe.find_handler()"""

    @pytest.fixture
    def app_with_handlers(self):
        """Create app with multiple handlers."""
        app = AnyServe()

        @app.capability(type="chat", model="llama-7b")
        def chat_7b(request, context):
            return "chat_7b"

        @app.capability(type="chat", model="llama-70b")
        def chat_70b(request, context):
            return "chat_70b"

        @app.capability(type="embed")
        def embed(request, context):
            return "embed"

        return app

    @pytest.mark.p0
    def test_find_handler_exact_match(self, app_with_handlers):
        """Test finding handler with exact match."""
        result = app_with_handlers.find_handler({"type": "chat", "model": "llama-70b"})

        assert result is not None
        handler, uses_context, cap = result
        assert cap.get("model") == "llama-70b"

    @pytest.mark.p0
    def test_find_handler_partial_match(self, app_with_handlers):
        """Test finding handler with partial match."""
        result = app_with_handlers.find_handler({"type": "embed"})

        assert result is not None
        handler, uses_context, cap = result
        assert cap.get("type") == "embed"

    @pytest.mark.p0
    def test_find_handler_no_match(self, app_with_handlers):
        """Test find_handler returns None when no match."""
        result = app_with_handlers.find_handler({"type": "nonexistent"})
        assert result is None

    @pytest.mark.p1
    def test_find_handler_returns_first_match(self, app_with_handlers):
        """Test find_handler returns first matching handler."""
        # Query that could match multiple handlers
        result = app_with_handlers.find_handler({"type": "chat"})

        # Should return the first registered chat handler
        assert result is not None


class TestCapabilityBackwardCompatibility:
    """Tests for backward compatibility between model and capability."""

    @pytest.mark.p1
    def test_capability_registers_in_model_registry(self):
        """Test @app.capability also registers in legacy model registry."""
        app = AnyServe()

        @app.capability(type="chat", model="demo")
        def handler(request, context):
            pass

        # Should be in legacy registry with type as model_name
        assert ("chat", "demo") in app._local_registry

    @pytest.mark.p1
    def test_capability_type_only_registers_without_version(self):
        """Test capability without model registers with None version."""
        app = AnyServe()

        @app.capability(type="embed")
        def handler(request, context):
            pass

        # Should be in registry with None version
        assert ("embed", None) in app._local_registry
