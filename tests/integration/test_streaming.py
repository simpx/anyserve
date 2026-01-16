"""
Integration tests for streaming inference (Phase 7).

Tests the complete streaming flow including:
- @app.capability(stream=True) decorator
- Stream class integration
- Handler lookup for streaming
"""

import pytest
import threading
import time
from anyserve import AnyServe
from anyserve.kserve import Stream, ModelInferRequest, InferInputTensor, InferTensorContents


class TestStreamingCapabilityDecorator:
    """Tests for @app.capability(stream=True) decorator integration."""

    def test_register_streaming_handler(self):
        """Test registering a streaming handler."""
        app = AnyServe()

        @app.capability(type="chat", stream=True)
        def stream_handler(request, context, stream):
            stream.send({"token": "test"})
            stream.close()

        # Verify handler is registered
        caps = app.get_capabilities()
        assert len(caps) == 1
        assert caps[0]["type"] == "chat"

    def test_find_stream_handler(self):
        """Test finding a streaming handler."""
        app = AnyServe()

        @app.capability(type="chat", stream=True)
        def stream_handler(request, context, stream):
            pass

        # Should find streaming handler
        result = app.find_stream_handler({"type": "chat"})
        assert result is not None
        handler, uses_context, cap = result
        assert handler is stream_handler
        assert uses_context is True

    def test_find_stream_handler_not_found(self):
        """Test find_stream_handler returns None when no match."""
        app = AnyServe()

        @app.capability(type="chat", stream=True)
        def stream_handler(request, context, stream):
            pass

        # Should not find handler for different type
        result = app.find_stream_handler({"type": "embed"})
        assert result is None

    def test_find_handler_excludes_stream(self):
        """Test find_handler (non-streaming) excludes streaming handlers."""
        app = AnyServe()

        @app.capability(type="chat", stream=True)
        def stream_handler(request, context, stream):
            pass

        # Non-streaming find_handler should not find streaming handler
        result = app.find_handler({"type": "chat"})
        assert result is None

    def test_find_any_handler_finds_stream(self):
        """Test find_any_handler finds streaming handlers."""
        app = AnyServe()

        @app.capability(type="chat", stream=True)
        def stream_handler(request, context, stream):
            pass

        # find_any_handler should find streaming handler
        result = app.find_any_handler({"type": "chat"})
        assert result is not None
        handler, uses_context, cap, is_stream = result
        assert is_stream is True

    def test_both_streaming_and_non_streaming(self):
        """Test app with both streaming and non-streaming handlers."""
        app = AnyServe()

        @app.capability(type="chat", stream=True)
        def stream_chat(request, context, stream):
            pass

        @app.capability(type="embed")
        def non_stream_embed(request, context):
            pass

        # Find streaming
        stream_result = app.find_stream_handler({"type": "chat"})
        assert stream_result is not None
        assert stream_result[0] is stream_chat

        # Find non-streaming
        non_stream_result = app.find_handler({"type": "embed"})
        assert non_stream_result is not None
        assert non_stream_result[0] is non_stream_embed


class TestStreamingHandlerExecution:
    """Tests for executing streaming handlers."""

    def test_streaming_handler_full_flow(self):
        """Test complete streaming handler execution flow."""
        app = AnyServe()
        received_tokens = []

        @app.capability(type="chat", stream=True)
        def stream_handler(request, context, stream):
            tokens = ["Hello", " ", "world", "!"]
            for i, token in enumerate(tokens):
                is_last = (i == len(tokens) - 1)
                stream.send({
                    "token": token,
                    "finish_reason": "stop" if is_last else ""
                })
            stream.close()

        # Create request
        request = ModelInferRequest(
            model_name="chat",
            id="test-001",
        )
        request.inputs.append(
            InferInputTensor(
                name="text",
                datatype="BYTES",
                shape=[1],
                contents=InferTensorContents(
                    bytes_contents=[b"Hello"]
                )
            )
        )

        # Find and execute handler
        result = app.find_stream_handler({"type": "chat"})
        assert result is not None

        handler, uses_context, cap = result
        stream = Stream()

        # Run handler in thread
        def run_handler():
            handler(request, None, stream)

        thread = threading.Thread(target=run_handler)
        thread.start()

        # Collect responses
        for response in stream.iter_responses():
            received_tokens.append(response["token"])

        thread.join()

        assert received_tokens == ["Hello", " ", "world", "!"]

    def test_streaming_handler_with_delay(self):
        """Test streaming handler with simulated token generation delay."""
        app = AnyServe()

        @app.capability(type="slow_chat", stream=True)
        def slow_stream_handler(request, context, stream):
            for i in range(3):
                time.sleep(0.05)  # Simulate processing
                stream.send({"index": i})
            stream.close()

        request = ModelInferRequest(model_name="slow_chat", id="test-002")

        result = app.find_stream_handler({"type": "slow_chat"})
        handler, _, _ = result
        stream = Stream()

        thread = threading.Thread(target=lambda: handler(request, None, stream))
        thread.start()

        responses = []
        start_time = time.time()
        for response in stream.iter_responses():
            responses.append(response)
        elapsed = time.time() - start_time

        thread.join()

        assert len(responses) == 3
        assert elapsed >= 0.15  # At least 3 * 0.05 seconds

    def test_streaming_handler_error(self):
        """Test streaming handler that encounters error."""
        app = AnyServe()

        @app.capability(type="error_stream", stream=True)
        def error_stream_handler(request, context, stream):
            stream.send({"token": "ok"})
            stream.error("Something went wrong")

        request = ModelInferRequest(model_name="error_stream", id="test-003")

        result = app.find_stream_handler({"type": "error_stream"})
        handler, _, _ = result
        stream = Stream()

        thread = threading.Thread(target=lambda: handler(request, None, stream))
        thread.start()

        responses = list(stream.iter_responses())
        thread.join()

        assert len(responses) == 2
        assert responses[0] == {"token": "ok"}
        assert responses[1] == {"error_message": "Something went wrong"}


class TestStreamingWithCapabilityMatching:
    """Tests for streaming with capability matching."""

    def test_stream_handler_with_multiple_attrs(self):
        """Test streaming handler with multiple capability attributes."""
        app = AnyServe()

        @app.capability(type="chat", model="gpt-4", stream=True)
        def gpt4_stream(request, context, stream):
            stream.send({"model": "gpt-4"})
            stream.close()

        @app.capability(type="chat", model="llama", stream=True)
        def llama_stream(request, context, stream):
            stream.send({"model": "llama"})
            stream.close()

        # Find gpt-4 handler
        result1 = app.find_stream_handler({"type": "chat", "model": "gpt-4"})
        assert result1 is not None
        assert result1[0] is gpt4_stream

        # Find llama handler
        result2 = app.find_stream_handler({"type": "chat", "model": "llama"})
        assert result2 is not None
        assert result2[0] is llama_stream

        # Partial match (type only) - should find first registered
        result3 = app.find_stream_handler({"type": "chat"})
        assert result3 is not None
