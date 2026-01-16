"""
AnyServe Basic Example - Test Client
=====================================

This client tests the three example models using the gRPC KServe v2 protocol.

Usage:
    1. Start server: python -m anyserve.cli examples.basic.app:app --port 8000
    2. Run client:   python examples/basic/test_client.py [--port PORT]
"""

import sys
import argparse
from anyserve.worker.client import Client


def test_add(client: Client):
    """Test the 'add' model."""
    print("Testing 'add' model...")

    result = client.infer(
        model_name="add",
        inputs={
            "a": [1, 2, 3],
            "b": [10, 20, 30]
        }
    )

    print(f"  Inputs: a=[1, 2, 3], b=[10, 20, 30]")
    print(f"  Result: {result.get('sum', [])}")


def test_echo(client: Client):
    """Test the 'echo' model."""
    print("Testing 'echo' model...")

    result = client.infer(
        model_name="echo",
        inputs={
            "text": [b"hello world"]
        }
    )

    print(f"  Input: text=b'hello world'")
    for key, value in result.items():
        print(f"  Output '{key}': {value}")


def test_classifier_v1(client: Client):
    """Test versioned model."""
    print("Testing 'classifier' v1...")

    result = client.infer(
        model_name="classifier",
        version="v1",
        inputs={
            "features": [1.0, 2.0, 3.0, 4.0]
        }
    )

    print(f"  Inputs: features=[1.0, 2.0, 3.0, 4.0]")
    print(f"  Predicted class: {result.get('class', [])}")


def main():
    parser = argparse.ArgumentParser(description="Test AnyServe basic example models")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--host", type=str, default="localhost", help="Server host (default: localhost)")
    args = parser.parse_args()

    target = f"{args.host}:{args.port}"
    print(f"=== AnyServe KServe Client Demo ===")
    print(f"Connecting to: {target}\n")

    # Create client
    client = Client(endpoint=target)

    # Check if server is alive
    if not client.is_alive():
        print(f"ERROR: Server at {target} is not responding")
        print("Please start the server first:")
        print("  python -m anyserve.cli examples.basic.app:app --port 8000")
        sys.exit(1)

    print("Server is alive!\n")

    # Run tests
    try:
        test_add(client)
        print()

        test_echo(client)
        print()

        test_classifier_v1(client)

        print("\n=== All tests completed ===")
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
