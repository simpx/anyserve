import sys
import os
import time
import anyserve
from anyserve import Any
from examples.shared import MyBigData

def main():
    root_dir = os.path.abspath("./tmp_distributed")
    # Clean up previous run if exists? No, other nodes use it.
    
    print(f"[Client] Starting on {root_dir}")
    
    # Client also needs to be a node to host the initial object
    anyserve.init(root_dir=root_dir, instance_id="client-node")
    
    # Give everyone a second to settle
    time.sleep(1)

    # 1. Create Object (Stored on Client Node)
    obj = Any(MyBigData(size=100000))
    print(f"[Client] Created Ref: {obj}")

    # 2. Call Service Step1 (Remote)
    print("[Client] Calling Service Step1...")
    result = anyserve.call("step1", obj)

    # 3. Result
    print(f"[Client] Final Result: {result}")

if __name__ == "__main__":
    main()
