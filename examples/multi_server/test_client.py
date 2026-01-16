"""
Multi-Server Example - Test Client
===================================

This client demonstrates the discovery mode of the Client class.
It connects to an API Server to discover Worker endpoints and then
calls multiple capabilities across different workers.

Prerequisites:
    1. Start the servers: ./examples/multi_server/run_server.sh
    2. Run this client:   ./examples/multi_server/run_client.sh

Capabilities tested:
    - multiply (Worker 1): Multiply two INT32 tensors
    - divide (Worker 2):   Divide two FP32 tensors
    - power (Worker 2):    Raise FP32 base to INT32 exponent
"""

import sys
from anyserve.worker.client import Client


API_SERVER = "http://localhost:8080"


def test_multiply():
    """Test multiply capability on Worker 1."""
    print("=" * 50)
    print("Testing 'multiply' capability (Worker 1)")
    print("=" * 50)

    client = Client(
        api_server=API_SERVER,
        capability={"type": "multiply"},
    )

    print(f"  Mode: {client.mode}")
    print(f"  Endpoint (before infer): {client.endpoint}")

    result = client.infer(
        model_name="multiply",
        inputs={
            "a": [2, 3, 4],
            "b": [10, 20, 30],
        }
    )

    print(f"  Endpoint (after infer): {client.endpoint}")
    print(f"  Replica ID: {client.replica_id}")
    print()
    print("  Inputs: a=[2, 3, 4], b=[10, 20, 30]")
    print(f"  Result: product={result.get('product', [])}")
    print("  Expected: [20, 60, 120]")

    client.close()
    print()


def test_divide():
    """Test divide capability on Worker 2."""
    print("=" * 50)
    print("Testing 'divide' capability (Worker 2)")
    print("=" * 50)

    client = Client(
        api_server=API_SERVER,
        capability={"type": "divide"},
    )

    print(f"  Mode: {client.mode}")

    result = client.infer(
        model_name="divide",
        inputs={
            "a": [10.0, 20.0, 30.0],
            "b": [2.0, 4.0, 5.0],
        }
    )

    print(f"  Endpoint: {client.endpoint}")
    print(f"  Replica ID: {client.replica_id}")
    print()
    print("  Inputs: a=[10.0, 20.0, 30.0], b=[2.0, 4.0, 5.0]")
    print(f"  Result: quotient={result.get('quotient', [])}")
    print("  Expected: [5.0, 5.0, 6.0]")

    client.close()
    print()


def test_power():
    """Test power capability on Worker 2."""
    print("=" * 50)
    print("Testing 'power' capability (Worker 2)")
    print("=" * 50)

    client = Client(
        api_server=API_SERVER,
        capability={"type": "power"},
    )

    print(f"  Mode: {client.mode}")

    result = client.infer(
        model_name="power",
        inputs={
            "base": [2.0, 3.0, 4.0],
            "exp": [2, 3, 2],
        }
    )

    print(f"  Endpoint: {client.endpoint}")
    print(f"  Replica ID: {client.replica_id}")
    print()
    print("  Inputs: base=[2.0, 3.0, 4.0], exp=[2, 3, 2]")
    print(f"  Result: result={result.get('result', [])}")
    print("  Expected: [4.0, 27.0, 16.0]")

    client.close()
    print()


def test_direct_mode():
    """Test direct mode connection (without API Server)."""
    print("=" * 50)
    print("Testing Direct Mode (no API Server)")
    print("=" * 50)

    client = Client(endpoint="localhost:50051")

    print(f"  Mode: {client.mode}")
    print(f"  Endpoint: {client.endpoint}")

    result = client.infer(
        model_name="multiply",
        inputs={
            "a": [5, 6],
            "b": [7, 8],
        }
    )

    print(f"  Result: product={result.get('product', [])}")
    print("  Expected: [35, 48]")

    client.close()
    print()


def main():
    print()
    print("=" * 50)
    print("AnyServe Multi-Server Client Demo")
    print("=" * 50)
    print()
    print(f"API Server: {API_SERVER}")
    print()

    try:
        # Test all capabilities via discovery mode
        test_multiply()
        test_divide()
        test_power()

        # Also test direct mode
        test_direct_mode()

        print("=" * 50)
        print("All tests completed successfully!")
        print("=" * 50)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
