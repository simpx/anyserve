#!/usr/bin/env python3
"""
anyServe MVP Step 1 Client

This client demonstrates the core anyServe functionality:
1. Local Hit: Client -> Node A ("small") -> Success
2. Delegation: Client -> Node A ("large") -> Scheduler lookup -> Node B -> Success
3. Object Ref: Large output -> File reference
"""
import os
import sys
import grpc

# Add the examples/step1 directory to path for generated stubs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anyserve_pb2
import anyserve_pb2_grpc

DATA_DIR = os.environ.get("ANYSERVE_DATA_DIR", "/tmp/anyserve_data")
NODE_A_PORT = 50051
NODE_B_PORT = 50052


def test_infer(host: str, port: int, capability: str, inputs: str, test_name: str):
    """Send an Infer request to a node."""
    print(f"\n### {test_name} ###")
    print(f">>> Target: {host}:{port}, capability='{capability}'")
    print(f">>> Input: '{inputs[:50]}...' (len={len(inputs)})")
    
    channel = grpc.insecure_channel(f"{host}:{port}")
    stub = anyserve_pb2_grpc.AnyServeStub(channel)
    
    request = anyserve_pb2.InferRequest(
        capability=capability,
        inputs=inputs.encode('utf-8'),
        input_refs=[]
    )
    
    try:
        response = stub.Infer(request, timeout=30)
        output = response.output.decode('utf-8') if response.output else ""
        
        print(f"<<< Response received!")
        print(f"    delegated: {response.delegated}")
        
        if output:
            print(f"    output: '{output[:80]}...' (len={len(output)})")
        
        if response.output_refs:
            print(f"    output_refs: {response.output_refs}")
            # Read the file content
            for ref in response.output_refs:
                path = os.path.join(DATA_DIR, ref)
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        content = f.read()
                    print(f"    [File {ref[:8]}...]: '{content[:80]}...' (len={len(content)})")
        
        print(f"<<< SUCCESS!")
        return response
        
    except grpc.RpcError as e:
        print(f"<<< ERROR: {e.code()}: {e.details()}")
        return None


def main():
    print("=" * 60)
    print("anyServe MVP Step 1 - Client Tests")
    print("=" * 60)
    
    # Test 1: Local Hit - Node A can handle "small"
    test_infer(
        host="127.0.0.1",
        port=NODE_A_PORT,
        capability="small",
        inputs="Hello World! This is a simple test.",
        test_name="Test 1: Local Hit (Node A -> small)"
    )
    
    # Test 2: Delegation - Node A cannot handle "large", should delegate to Node B
    test_infer(
        host="127.0.0.1",
        port=NODE_A_PORT,
        capability="large",
        inputs="Process this with heavy capability please.",
        test_name="Test 2: Delegation (Node A -> large -> Node B)"
    )
    
    # Test 3: Direct to Node B - should handle locally
    test_infer(
        host="127.0.0.1",
        port=NODE_B_PORT,
        capability="large",
        inputs="Direct large request to Node B.",
        test_name="Test 3: Direct (Node B -> large)"
    )
    
    # Test 4: Object Ref - large output should go to file
    test_infer(
        host="127.0.0.1",
        port=NODE_B_PORT,
        capability="large",
        inputs="make_huge_data" + ("x" * 500),
        test_name="Test 4: Object Ref (Large Output -> File)"
    )
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
