#!/usr/bin/env python3
"""
AnyServe Basic Example Runner
==============================

This script demonstrates the complete workflow:
1. Start the AnyServe server with example models
2. Wait for server to be ready
3. Run test client to verify all models work
4. Cleanup on exit

Usage:
    python examples/basic/run_example.py
"""

import os
import sys
import subprocess
import time
import signal

def main():
    """Run the complete example with server and client."""
    print("=" * 70)
    print("AnyServe Basic Example - Complete Workflow")
    print("=" * 70)

    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Start server process
    print("\n[1/3] Starting AnyServe server...")
    print("      Models: echo, add, classifier:v1")
    print("      Port: 8000")

    server_process = subprocess.Popen(
        [sys.executable, "-m", "anyserve.cli", "examples.basic.app:app", "--port", "8000", "--workers", "1"],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Wait for server to be ready
    print("\n[2/3] Waiting for server to be ready...")
    max_wait = 10  # seconds
    start_time = time.time()
    server_ready = False

    try:
        while time.time() - start_time < max_wait:
            # Check if process crashed
            if server_process.poll() is not None:
                print("ERROR: Server process terminated unexpectedly")
                print("\nServer output:")
                if server_process.stdout:
                    print(server_process.stdout.read())
                sys.exit(1)

            # Try to connect to see if server is ready
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', 8000))
                sock.close()
                if result == 0:
                    server_ready = True
                    break
            except Exception:
                pass

            time.sleep(0.5)
            print(".", end="", flush=True)

        print()

        if not server_ready:
            print("ERROR: Server failed to start within timeout")
            server_process.terminate()
            sys.exit(1)

        print("      Server is ready!")

        # Run client tests
        print("\n[3/3] Running test client...")
        print("-" * 70)

        client_process = subprocess.run(
            [sys.executable, "examples/basic/test_client.py"],
            cwd=project_root,
            capture_output=False
        )

        print("-" * 70)

        if client_process.returncode == 0:
            print("\n" + "=" * 70)
            print("SUCCESS: All tests passed!")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("ERROR: Some tests failed")
            print("=" * 70)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    finally:
        # Cleanup: stop server
        print("\nStopping server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_process.kill()
        print("Done.")


if __name__ == "__main__":
    main()
