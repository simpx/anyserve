"""
Unit tests for Stream class in kserve.py.

Tests streaming functionality for Phase 7 implementation.
"""

import pytest
import threading
import time
from anyserve.kserve import Stream


class TestStream:
    """Tests for Stream class."""

    def test_stream_init(self):
        """Test Stream initialization."""
        stream = Stream()
        assert stream._closed is False
        assert stream._error is None
        assert stream._queue is not None

    def test_stream_send(self):
        """Test sending messages to stream."""
        stream = Stream()

        # Send a message
        stream.send({"token": "Hello"})

        # Verify it's in the queue
        item = stream._queue.get_nowait()
        assert item == {"token": "Hello"}

    def test_stream_send_multiple(self):
        """Test sending multiple messages."""
        stream = Stream()

        messages = [{"token": "Hello"}, {"token": " "}, {"token": "world"}]
        for msg in messages:
            stream.send(msg)

        # Retrieve all messages
        received = []
        for _ in range(len(messages)):
            received.append(stream._queue.get_nowait())

        assert received == messages

    def test_stream_close(self):
        """Test closing stream."""
        stream = Stream()
        stream.send({"token": "test"})
        stream.close()

        assert stream._closed is True

        # Queue should have the message plus sentinel None
        item1 = stream._queue.get_nowait()
        item2 = stream._queue.get_nowait()

        assert item1 == {"token": "test"}
        assert item2 is None  # Sentinel value

    def test_stream_send_after_close_raises(self):
        """Test that sending after close raises error."""
        stream = Stream()
        stream.close()

        with pytest.raises(RuntimeError, match="Cannot send to a closed stream"):
            stream.send({"token": "should fail"})

    def test_stream_error(self):
        """Test sending error response."""
        stream = Stream()
        stream.error("Something went wrong")

        assert stream._error == "Something went wrong"
        assert stream._closed is True

        # Check error message was queued
        item = stream._queue.get_nowait()
        assert item == {"error_message": "Something went wrong"}

    def test_stream_iter_responses(self):
        """Test iter_responses generator."""
        stream = Stream()

        # Send messages in a thread
        def sender():
            for i in range(3):
                stream.send({"index": i})
                time.sleep(0.01)
            stream.close()

        thread = threading.Thread(target=sender)
        thread.start()

        # Collect responses
        responses = list(stream.iter_responses())
        thread.join()

        assert len(responses) == 3
        assert responses[0] == {"index": 0}
        assert responses[1] == {"index": 1}
        assert responses[2] == {"index": 2}

    def test_stream_iterator_protocol(self):
        """Test Stream implements iterator protocol."""
        stream = Stream()

        stream.send({"a": 1})
        stream.send({"b": 2})
        stream.close()

        # Use iterator protocol
        items = []
        for item in stream:
            items.append(item)

        assert len(items) == 2
        assert items[0] == {"a": 1}
        assert items[1] == {"b": 2}

    def test_stream_next_raises_stopiteration(self):
        """Test StopIteration when stream is closed."""
        stream = Stream()
        stream.close()

        with pytest.raises(StopIteration):
            next(stream)

    def test_stream_threaded_producer_consumer(self):
        """Test stream in producer-consumer pattern."""
        stream = Stream()
        results = []

        def producer():
            for i in range(5):
                stream.send({"value": i * 10})
                time.sleep(0.01)
            stream.close()

        def consumer():
            for response in stream.iter_responses():
                results.append(response["value"])

        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join()
        consumer_thread.join()

        assert results == [0, 10, 20, 30, 40]


class TestStreamWithProto:
    """Tests for Stream with proto-like objects."""

    def test_stream_with_mock_proto(self):
        """Test stream with mock proto response objects."""
        stream = Stream()

        # Simulate proto-like objects
        class MockProtoResponse:
            def __init__(self, text, is_final):
                self.text = text
                self.is_final = is_final

        responses = [
            MockProtoResponse("Hello", False),
            MockProtoResponse(" world", False),
            MockProtoResponse("!", True),
        ]

        for resp in responses:
            stream.send(resp)
        stream.close()

        received = list(stream.iter_responses())
        assert len(received) == 3
        assert received[0].text == "Hello"
        assert received[1].text == " world"
        assert received[2].text == "!"
        assert received[2].is_final is True

    def test_stream_error_handling_in_consumer(self):
        """Test error handling when consumer encounters error."""
        stream = Stream()

        def producer():
            stream.send({"data": "ok"})
            time.sleep(0.01)
            stream.error("Producer error occurred")

        thread = threading.Thread(target=producer)
        thread.start()

        responses = list(stream.iter_responses())
        thread.join()

        assert len(responses) == 2
        assert responses[0] == {"data": "ok"}
        assert responses[1] == {"error_message": "Producer error occurred"}
