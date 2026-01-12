import os
import uuid
import random
from typing import Optional

try:
    from anyserve._core import AnyserveCore
except ImportError:
    from ._core import AnyserveCore

_global_core: Optional[AnyserveCore] = None

def init(dispatcher: object, root_dir: str = "./tmp_anyserve", instance_id: Optional[str] = None, port: int = 0):
    global _global_core
    if instance_id is None:
        instance_id = str(uuid.uuid4())
    
    if port == 0:
        # Pick random port between 10000-20000 for PoC safe range
        port = random.randint(10000, 20000)
    
    # Ensure absolute path
    root_dir = os.path.abspath(root_dir)
    print(f"[Anyserve] Initializing node {instance_id} at {root_dir}")
    print(f"[Anyserve] gRPC Server starting on port {port}")
    
    _global_core = AnyserveCore(root_dir, instance_id, port, dispatcher)
    return _global_core

def get_core() -> AnyserveCore:
    if _global_core is None:
        raise RuntimeError("Anyserve not initialized. Call anyserve.init() first.")
    return _global_core
