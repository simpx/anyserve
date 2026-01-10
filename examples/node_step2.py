import sys
import os
import time
import anyserve
from anyserve import Any
from examples.shared import MyBigData

# Service step2: Consumer
@anyserve.service(name="step2")
def step2(data: Any[MyBigData]):
    print(f"[Step2] Received data ref: {data}")
    real_data = data.get()
    print(f"[Step2] Processed payload size: {len(real_data.payload)}")
    return "Result from Step2"

def main():
    root_dir = os.path.abspath("./tmp_distributed")
    print(f"[Node Step2] Starting on {root_dir}")
    
    # Init with specific ID to be safe or random
    anyserve.init(root_dir=root_dir, instance_id="node-step2")
    
    print("[Node Step2] Serving forever...")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
