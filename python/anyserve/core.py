import os
import uuid
from typing import Optional
from anyserve._core import AnyserveCore

_global_core: Optional[AnyserveCore] = None

def init(root_dir: str = "./tmp_anyserve", instance_id: Optional[str] = None):
    global _global_core
    if instance_id is None:
        instance_id = str(uuid.uuid4())
    
    # Ensure absolute path
    root_dir = os.path.abspath(root_dir)
    print(f"[Anyserve] Initializing node {instance_id} at {root_dir}")
    
    _global_core = AnyserveCore(root_dir, instance_id)
    return _global_core

def get_core() -> AnyserveCore:
    if _global_core is None:
        raise RuntimeError("Anyserve not initialized. Call anyserve.init() first.")
    return _global_core
