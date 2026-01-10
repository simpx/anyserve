"""
Replica H1: Heavy decode capability

This replica can serve 'decode.heavy' requests locally.
It is designed for heavy/complex decoding tasks.
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

# Capability: decode.heavy (heavy/complex decoding)
@anyserve.capability(name="decode.heavy")
def decode_heavy_handler(data: Any[DecodeInput]):
    print(f"[H1:decode.heavy] Received heavy decode request: {data}")
    real_data = data.get()
    print(f"[H1:decode.heavy] Processing heavy task: {real_data}")
    
    # Simulate heavy processing
    result = f"Heavy Decoded: {real_data.text[:50]}... (len={len(real_data.text)}, complexity={real_data.complexity}, processed_by=H1)"
    print(f"[H1:decode.heavy] Result: {result}")
    return result

def main():
    root_dir = os.path.abspath("./tmp_mvp")
    print(f"[Replica H1] Starting on {root_dir}")
    
    anyserve.init(root_dir=root_dir, instance_id="replica-h1")
    
    print("[Replica H1] Serving capabilities: decode.heavy")
    print("[Replica H1] Serving forever...")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
