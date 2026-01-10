"""
MVP Demo Client

This client demonstrates:
1. Sending a 'decode' request -> S1 executes locally
2. Sending a 'decode.heavy' request -> H1 executes (direct)
3. Sending a 'decode' request that S1 delegates to H1 when it's too complex
"""
import sys
import os
import time
import anyserve
from anyserve import Any
from anyserve.core import get_core

# Data class for demo
class DecodeInput:
    def __init__(self, text: str, complexity: int = 1):
        self.text = text
        self.complexity = complexity

    def __repr__(self):
        return f"<DecodeInput text_len={len(self.text)} complexity={self.complexity}>"

def main():
    root_dir = os.path.abspath("./tmp_mvp")
    
    print(f"[Client] Starting on {root_dir}")
    
    # Client also needs to be a node to host the initial object
    anyserve.init(root_dir=root_dir, instance_id="client-node")
    
    # Give replicas time to register
    time.sleep(1)

    print("\n" + "="*60)
    print("Demo Scenario 1: decode request -> S1 local execution")
    print("="*60)
    
    # Create input object
    input1 = Any(DecodeInput(text="Hello World! " * 100, complexity=1))
    print(f"[Client] Created input ref: {input1}")
    
    # Call 'decode' capability - should be handled by S1 locally
    print("[Client] Calling 'decode' capability...")
    result1 = anyserve.call("decode", input1)
    print(f"[Client] Result: {result1}")

    print("\n" + "="*60)
    print("Demo Scenario 2: decode.heavy request -> H1 executes directly")
    print("="*60)
    
    # Create input object for heavy task
    input2 = Any(DecodeInput(text="Complex data " * 500, complexity=10))
    print(f"[Client] Created input ref: {input2}")
    
    # Call 'decode.heavy' capability - should be handled by H1 directly
    print("[Client] Calling 'decode.heavy' capability...")
    result2 = anyserve.call("decode.heavy", input2)
    print(f"[Client] Result: {result2}")

    print("\n" + "="*60)
    print("Demo Scenario 3: Request to S1's endpoint for decode.heavy")
    print("              -> S1 detects hard mismatch, upgrades & delegates to H1")
    print("="*60)
    
    # This scenario demonstrates delegation:
    # We directly call S1's endpoint with decode.heavy
    # S1 doesn't have decode.heavy capability locally
    # S1 detects hard mismatch, upgrades the capability and delegates to H1
    
    input3 = Any(DecodeInput(text="Delegated task " * 300, complexity=20))
    print(f"[Client] Created input ref: {input3}")
    
    # Get S1's address and call it directly with decode.heavy
    core = get_core()
    s1_endpoints = core.lookup_capability("decode")
    if s1_endpoints:
        s1_addr = s1_endpoints[0]
        print(f"[Client] Found S1 at: {s1_addr}")
        print(f"[Client] Sending 'decode.heavy' request directly to S1...")
        print(f"[Client] S1 should detect it can't serve decode.heavy and delegate to H1")
        
        import pickle
        args_pickle = pickle.dumps((input3,))
        result_pickle = core.remote_call(s1_addr, "decode.heavy", args_pickle, False)
        result3 = pickle.loads(bytes(result_pickle))
        print(f"[Client] Result: {result3}")
    else:
        print("[Client] S1 not found, skipping scenario 3")

    print("\n" + "="*60)
    print("MVP Demo Complete!")
    print("="*60)

if __name__ == "__main__":
    main()
