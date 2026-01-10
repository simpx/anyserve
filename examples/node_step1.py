import sys
import os
import time
import anyserve
from anyserve import Any
from examples.shared import MyBigData

# Service step1: Proxy
@anyserve.service(name="step1")
def step1(data: Any[MyBigData]):
    print(f"[Step1] Received request. Passing through to Step2...")
    return anyserve.call("step2", data)

def main():
    root_dir = os.path.abspath("./tmp_distributed")
    print(f"[Node Step1] Starting on {root_dir}")
    
    anyserve.init(root_dir=root_dir, instance_id="node-step1")
    
    print("[Node Step1] Serving forever...")
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
