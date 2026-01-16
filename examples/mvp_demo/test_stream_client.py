#!/usr/bin/env python3
"""
Streaming Test Client - Test streaming inference endpoint.

Usage:
    python examples/mvp_demo/test_stream_client.py

Prerequisites:
    1. Start API Server: python api_server/main.py --port 8080
    2. Start streaming worker: anyserve examples.mvp_demo.stream_app:app --port 50051 --api-server http://localhost:8080
"""

import httpx
import json
import sys

API_SERVER = "http://localhost:8080"


def test_streaming():
    """Test streaming inference endpoint."""
    print("=" * 60)
    print("Testing Streaming Inference")
    print("=" * 60)

    request_data = {
        "model_name": "chat",
        "id": "stream-test-001",
        "inputs": [
            {
                "name": "text",
                "datatype": "BYTES",
                "shape": [1],
                "contents": {
                    "bytes_contents": ["Tell me a story"]
                }
            }
        ]
    }

    print(f"\nRequest: POST {API_SERVER}/infer/stream")
    print(f"Headers: X-Capability-Type: chat")
    print(f"Body: {json.dumps(request_data, indent=2)}")
    print("\nStreaming response:")
    print("-" * 40)

    tokens = []
    finish_reason = ""

    try:
        with httpx.stream(
            "POST",
            f"{API_SERVER}/infer/stream",
            headers={
                "Content-Type": "application/json",
                "X-Capability-Type": "chat",
            },
            json=request_data,
            timeout=30.0,
        ) as response:
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print()

            for line in response.iter_lines():
                if not line:
                    continue

                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    try:
                        data = json.loads(data_str)

                        # Check for error
                        if "error" in data:
                            print(f"  ERROR: {data['error']}")
                            continue

                        # Extract text_output and finish_reason
                        text_output = ""
                        for output in data.get("outputs", []):
                            if output["name"] == "text_output":
                                contents = output.get("contents", {})
                                if "bytes_contents" in contents:
                                    text_output = contents["bytes_contents"][0]
                            elif output["name"] == "finish_reason":
                                contents = output.get("contents", {})
                                if "bytes_contents" in contents:
                                    finish_reason = contents["bytes_contents"][0]

                        tokens.append(text_output)
                        status = f" [DONE]" if finish_reason == "stop" else ""
                        print(f"  Token: '{text_output}'{status}")

                        if finish_reason == "stop":
                            break

                    except json.JSONDecodeError as e:
                        print(f"  Failed to parse: {data_str} - {e}")

    except httpx.ConnectError as e:
        print(f"\nConnection error: {e}")
        print("\nMake sure the API Server and streaming worker are running:")
        print("  1. python api_server/main.py --port 8080")
        print("  2. anyserve examples.mvp_demo.stream_app:app --port 50051 --api-server http://localhost:8080")
        return False
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("-" * 40)
    full_text = "".join(tokens)
    print(f"\nFull response: '{full_text}'")
    print(f"Finish reason: '{finish_reason}'")

    # Verify
    expected = "Hello world! This is streaming."
    success = full_text == expected and finish_reason == "stop"

    print()
    if success:
        print("TEST PASSED")
    else:
        print("TEST FAILED")
        if full_text != expected:
            print(f"  Expected text: '{expected}'")
            print(f"  Got: '{full_text}'")
        if finish_reason != "stop":
            print(f"  Expected finish_reason: 'stop'")
            print(f"  Got: '{finish_reason}'")

    return success


def test_non_streaming():
    """Test non-streaming endpoint for comparison."""
    print("\n" + "=" * 60)
    print("Testing Non-Streaming Inference (for comparison)")
    print("=" * 60)

    request_data = {
        "model_name": "echo",
        "id": "echo-test-001",
        "inputs": [
            {
                "name": "text",
                "datatype": "BYTES",
                "shape": [1],
                "contents": {
                    "bytes_contents": ["Hello from test client"]
                }
            }
        ]
    }

    print(f"\nRequest: POST {API_SERVER}/infer/json")
    print(f"Headers: X-Capability-Type: echo")

    try:
        response = httpx.post(
            f"{API_SERVER}/infer/json",
            headers={
                "Content-Type": "application/json",
                "X-Capability-Type": "echo",
            },
            json=request_data,
            timeout=10.0,
        )

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"Error: {response.text}")
            return False

    except httpx.ConnectError as e:
        print(f"Connection error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    print("AnyServe Streaming Test Client")
    print()

    streaming_ok = test_streaming()
    # non_streaming_ok = test_non_streaming()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Streaming test: {'PASS' if streaming_ok else 'FAIL'}")
    # print(f"Non-streaming test: {'PASS' if non_streaming_ok else 'FAIL'}")

    sys.exit(0 if streaming_ok else 1)
