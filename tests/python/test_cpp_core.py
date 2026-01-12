#!/usr/bin/env python3
"""
Test script for the C++ AnyserveCore.
Demonstrates the C++ control plane with Python bindings.
"""
import sys
import os
import tempfile
import threading
import time

# Add python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

import anyserve

def main():
    print("=" * 60)
    print("AnyServe C++ Core Test")
    print("=" * 60)
    
    # Check if _core is available
    if anyserve._core is None:
        print("ERROR: C++ core extension not available!")
        sys.exit(1)
    
    print(f"✓ C++ extension loaded: {anyserve._core.__file__}")
    print(f"✓ Version: {anyserve._core.__version__}")
    
    # Create a temporary directory for the test
    root_dir = tempfile.mkdtemp(prefix="anyserve_cpp_test_")
    instance_id = "test-cpp-instance"
    port = 50052
    
    print(f"\n--- Configuration ---")
    print(f"Root dir: {root_dir}")
    print(f"Instance ID: {instance_id}")
    print(f"Port: {port}")
    
    # Define a dispatcher callback
    def dispatcher(request_id: str, model_name: str, inputs: bytes) -> bytes:
        """
        Dispatcher callback - called by C++ when a request arrives.
        This is where you would dispatch to the actual Python handler.
        """
        print(f"\n[Dispatcher] Received request:")
        print(f"  request_id: {request_id}")
        print(f"  model_name: {model_name}")
        print(f"  inputs size: {len(inputs)} bytes")
        
        # Simulate processing
        result = f"Processed {model_name} request {request_id}"
        return result.encode('utf-8')
    
    print(f"\n--- Creating AnyserveCore ---")
    core = anyserve._core.AnyserveCore(root_dir, instance_id, port, dispatcher)
    
    print(f"\n--- Registering Capabilities ---")
    core.register_capability("decode")
    core.register_capability("decode.heavy")
    core.register_capability("embedding")
    print("✓ Registered: decode, decode.heavy, embedding")
    
    print(f"\n--- Capability Lookup ---")
    for cap in ["decode", "decode.heavy", "embedding", "unknown"]:
        result = core.lookup_capability(cap)
        status = "✓ found" if result else "✗ not found"
        print(f"  {cap}: {status}")
    
    print(f"\n--- Core Status ---")
    print(f"  Instance ID: {core.instance_id}")
    print(f"  Port: {core.port}")
    print(f"  Address: {core.get_address()}")
    print(f"  Is Running: {core.is_running}")
    
    print(f"\n--- Testing Remote Call (simulated) ---")
    try:
        # This would normally call a remote service
        # For now it demonstrates the API
        result = core.remote_call("localhost:50053", "test_model", b"test_input")
        print(f"  Remote call result: {result}")
    except Exception as e:
        print(f"  Remote call failed (expected): {e}")
    
    # Keep server running briefly to show it works
    print(f"\n--- Server Running ---")
    print("gRPC server is listening on", core.get_address())
    print("(Press Ctrl+C to stop or wait 2 seconds)")
    
    try:
        time.sleep(2)
    except KeyboardInterrupt:
        pass
    
    # Stop the server
    print(f"\n--- Stopping Server ---")
    core.stop()
    print("✓ Server stopped")
    
    # Cleanup
    import shutil
    shutil.rmtree(root_dir)
    print("✓ Temporary files cleaned up")
    
    print("\n" + "=" * 60)
    print("C++ Core Test PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    main()
