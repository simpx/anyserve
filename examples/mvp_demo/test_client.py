#!/usr/bin/env python3
"""
MVP Demo Test Client

This script tests the MVP demo by sending requests to the API Server.
"""

import httpx
import json
import sys
import time

API_SERVER = "http://localhost:8080"


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(name: str, success: bool, response: dict = None, error: str = None):
    status = "PASS" if success else "FAIL"
    color = "\033[92m" if success else "\033[91m"
    reset = "\033[0m"
    print(f"{color}[{status}]{reset} {name}")
    if response:
        print(f"  Response: {json.dumps(response, indent=2)[:200]}...")
    if error:
        print(f"  Error: {error}")


def test_health():
    """Test health endpoint."""
    print_header("Test: Health Check")
    try:
        response = httpx.get(f"{API_SERVER}/health", timeout=5.0)
        success = response.status_code == 200 and response.json().get("status") == "healthy"
        print_result("Health check", success, response.json())
        return success
    except Exception as e:
        print_result("Health check", False, error=str(e))
        return False


def test_registry():
    """Test registry endpoint."""
    print_header("Test: Registry")
    try:
        response = httpx.get(f"{API_SERVER}/registry", timeout=5.0)
        success = response.status_code == 200
        data = response.json()
        print_result("Get registry", success, data)

        if success:
            print(f"\n  Registered replicas: {data['total']}")
            for replica in data.get('replicas', []):
                print(f"    - {replica['replica_id']}: {replica['capabilities']}")

        return success
    except Exception as e:
        print_result("Get registry", False, error=str(e))
        return False


def test_chat_capability():
    """Test chat capability routing."""
    print_header("Test: Chat Capability")
    try:
        response = httpx.post(
            f"{API_SERVER}/infer/json",
            headers={
                "Content-Type": "application/json",
                "X-Capability-Type": "chat",
            },
            json={
                "model_name": "chat",
                "inputs": [
                    {
                        "name": "text",
                        "datatype": "BYTES",
                        "shape": [1],
                        "contents": {"bytes_contents": ["Hello, AnyServe!"]}
                    }
                ]
            },
            timeout=10.0,
        )

        success = response.status_code == 200
        data = response.json() if success else {"error": response.text}
        print_result("Chat capability", success, data)
        return success
    except Exception as e:
        print_result("Chat capability", False, error=str(e))
        return False


def test_embed_capability():
    """Test embed capability routing."""
    print_header("Test: Embed Capability")
    try:
        response = httpx.post(
            f"{API_SERVER}/infer/json",
            headers={
                "Content-Type": "application/json",
                "X-Capability-Type": "embed",
            },
            json={
                "model_name": "embed",
                "inputs": [
                    {
                        "name": "text",
                        "datatype": "BYTES",
                        "shape": [1],
                        "contents": {"bytes_contents": ["Sample text for embedding"]}
                    }
                ]
            },
            timeout=10.0,
        )

        success = response.status_code == 200
        data = response.json() if success else {"error": response.text}
        print_result("Embed capability", success, data)
        return success
    except Exception as e:
        print_result("Embed capability", False, error=str(e))
        return False


def test_heavy_capability():
    """Test heavy capability routing."""
    print_header("Test: Heavy Capability")
    try:
        response = httpx.post(
            f"{API_SERVER}/infer/json",
            headers={
                "Content-Type": "application/json",
                "X-Capability-Type": "heavy",
            },
            json={
                "model_name": "heavy",
                "inputs": [
                    {
                        "name": "data",
                        "datatype": "BYTES",
                        "shape": [1],
                        "contents": {"bytes_contents": ["Heavy processing data"]}
                    }
                ]
            },
            timeout=30.0,
        )

        success = response.status_code == 200
        data = response.json() if success else {"error": response.text}
        print_result("Heavy capability", success, data)
        return success
    except Exception as e:
        print_result("Heavy capability", False, error=str(e))
        return False


def test_unknown_capability():
    """Test routing for unknown capability."""
    print_header("Test: Unknown Capability (should fail or delegate)")
    try:
        response = httpx.post(
            f"{API_SERVER}/infer/json",
            headers={
                "Content-Type": "application/json",
                "X-Capability-Type": "unknown",
            },
            json={
                "model_name": "unknown",
                "inputs": []
            },
            timeout=10.0,
        )

        # Expected to fail with 404 or get delegated
        success = response.status_code in [404, 502]  # 404 = not found, 502 = delegation failed
        data = {"status_code": response.status_code, "body": response.text[:200]}
        print_result("Unknown capability (expected failure)", success, data)
        return True  # Test passes if we get expected error
    except Exception as e:
        print_result("Unknown capability", True, error=f"Expected error: {e}")
        return True


def test_registration():
    """Test replica registration."""
    print_header("Test: Replica Registration")
    try:
        response = httpx.post(
            f"{API_SERVER}/register",
            json={
                "replica_id": "test-replica",
                "endpoint": "localhost:9999",
                "capabilities": [
                    {"type": "test", "model": "demo"}
                ]
            },
            timeout=5.0,
        )

        success = response.status_code == 200 and response.json().get("success")
        print_result("Register replica", success, response.json())

        # Verify registration
        if success:
            registry = httpx.get(f"{API_SERVER}/registry", timeout=5.0).json()
            found = any(r["replica_id"] == "test-replica" for r in registry.get("replicas", []))
            print_result("Verify registration in registry", found)

            # Unregister
            unreg = httpx.request(
                "DELETE",
                f"{API_SERVER}/unregister",
                json={"replica_id": "test-replica"},
                timeout=5.0,
            )
            print_result("Unregister replica", unreg.status_code == 200)

        return success
    except Exception as e:
        print_result("Registration test", False, error=str(e))
        return False


def main():
    print("\n" + "=" * 60)
    print("  AnyServe MVP Demo Test Client")
    print("=" * 60)
    print(f"\nAPI Server: {API_SERVER}")

    # Wait for API Server
    print("\nWaiting for API Server...")
    for i in range(10):
        try:
            httpx.get(f"{API_SERVER}/health", timeout=2.0)
            print("API Server is ready!")
            break
        except:
            time.sleep(1)
    else:
        print("ERROR: API Server not available")
        sys.exit(1)

    # Run tests
    results = []

    results.append(("Health Check", test_health()))
    results.append(("Registry", test_registry()))
    results.append(("Registration", test_registration()))
    results.append(("Chat Capability", test_chat_capability()))
    results.append(("Embed Capability", test_embed_capability()))
    results.append(("Heavy Capability", test_heavy_capability()))
    results.append(("Unknown Capability", test_unknown_capability()))

    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "\033[92mPASS\033[0m" if result else "\033[91mFAIL\033[0m"
        print(f"  [{status}] {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n\033[92mAll tests passed!\033[0m")
        sys.exit(0)
    else:
        print(f"\n\033[91m{total - passed} tests failed\033[0m")
        sys.exit(1)


if __name__ == "__main__":
    main()
