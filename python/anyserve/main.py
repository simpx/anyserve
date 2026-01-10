import anyserve
from anyserve import Any
import os

# Data class
class MyBigData:
    def __init__(self, size):
        self.payload = "x" * size

# Service step2: Consumer
@anyserve.service(name="step2")
def step2(data: Any[MyBigData]):
    print(f"[Step2] Received data ref: {data}")
    real_data = data.get()
    print(f"[Step2] Processed payload size: {len(real_data.payload)}")
    return "Result from Step2"

# Service step1: Proxy
@anyserve.service(name="step1")
def step1(data: Any[MyBigData]):
    print("[Step1] Passing through...")
    return anyserve.call("step2", data)

def main():
    # 1. Init
    anyserve.init(root_dir="./tmp_anyserve")

    # 2. Create Object
    obj = Any(MyBigData(size=100000))
    print(f"[Client] Created Ref: {obj}")

    # 3. Call Service
    result = anyserve.call("step1", obj)

    # 4. Result
    print(f"[Client] Final Result: {result}")

if __name__ == "__main__":
    main()
