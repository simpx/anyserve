"""
Replica S1: Standard decode capability

This replica can serve 'decode' requests locally.
When it receives a 'decode.heavy' request (which it cannot serve locally),
it will delegate to a replica that can (H1).
"""
import sys
import os
import time
import anyserve
from anyserve import Any

# Data class for demo
class DecodeInput:
    def __init__(self, text: str, complexity: int = 1):
        self.text = text
        self.complexity = complexity

    def __repr__(self):
        return f"<DecodeInput text_len={len(self.text)} complexity={self.complexity}>"

# Capability: decode (standard)
# This replica CAN serve 'decode' locally
@anyserve.capability(name="decode")
def decode_handler(data: Any[DecodeInput]):
    print(f"[S1:decode] Received decode request: {data}")
    real_data = data.get()
    print(f"[S1:decode] Processing: {real_data}")
    
    # Simple decode simulation
    result = f"Decoded: {real_data.text[:50]}... (len={len(real_data.text)}, complexity={real_data.complexity})"
    print(f"[S1:decode] Result: {result}")
    return result

def main():
    root_dir = os.path.abspath("./tmp_mvp")
    print(f"[Replica S1] Starting on {root_dir}")
    
    # Register the upgrade path for delegation:
    # When S1 receives a request for 'decode.heavy' that it cannot serve locally,
    # it upgrades to 'decode.heavy' and routes to a replica that has this capability.
    # Note: Since decode.heavy IS the target, we need S1 to be an entry point for it.
    anyserve.register_upgrade("decode.heavy", "decode.heavy")
    
    anyserve.init(root_dir=root_dir, instance_id="replica-s1")
    
    print("[Replica S1] Serving capabilities: decode")
    print("[Replica S1] Entry point for: decode.heavy (will delegate to H1)")
    print("[Replica S1] Serving forever...")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
