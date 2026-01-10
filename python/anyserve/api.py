import random
import functools
from typing import Callable, Any as PyAny
from anyserve.core import get_core, init as core_init
from anyserve.objects import Any

# Global registry for local function implementations
# In a real system, this is not needed on the client side, only on the worker side.
_local_services = {}

def init(root_dir: str = "./tmp_anyserve", instance_id: str = None):
    """Initialize the Anyserve node."""
    return core_init(root_dir, instance_id)

def service(name: str):
    """
    Decorator to register a service.
    """
    def decorator(func: Callable):
        # 1. Register to local memory registry (so we can execute it if called)
        _local_services[name] = func
        
        # 2. Register to Global Name Service (via Rust)
        # Note: This requires init() to be called before @service definition 
        # OR we delay registration until init?
        # For simplicity in this PoC, we assume init() is called early or we lazy register?
        # Actually, Python decorators run at import time. init() runs at runtime.
        # We should just register to _local_services here.
        # And when `call` encounters it, or we have an explicit `serve()` function?
        # The user example calls `anyserve.init()` in `main()`.
        # So we can't call Rust store in the decorator if it runs before main.
        
        # Let's change strategy: The decorator just marks the function.
        # Registration happens either lazily or we assume the user runs structure carefully.
        # User example:
        # @service...
        # def main(): init(); ...
        
        # So at decorator time, core is NOT initialized.
        # We'll just store the func in _local_services.
        
        # BUT, we need to register with Rust eventually so `call` can find it.
        # Let's add an `register_services()` function or do it in `init()`?
        # Or checking `_local_services` in `init` and registering them all?
        return func
    return decorator

def _register_all_local_services():
    """Helper to register all decorated services to the Rust NameService."""
    core = get_core()
    for name in _local_services:
        core.register_service(name)
        print(f"[Anyserve] Registered local service: {name}")

# Wrap core_init to also register services
def init(root_dir: str = "./tmp_anyserve", instance_id: str = None):
    core = core_init(root_dir, instance_id)
    _register_all_local_services()
    return core

def call(service_name: str, *args):
    """
    Call a service by name.
    """
    core = get_core()
    
    # 1. Service Discovery
    instances = core.lookup_service(service_name)
    if not instances:
        raise RuntimeError(f"Service '{service_name}' not found")
    
    # 2. Load Balancing (Random)
    target_instance = random.choice(instances)
    
    # 3. Execution (RPC)
    # In this single-process PoC, we simulate RPC by looking up the local function.
    # In a real system, we would send a request to `target_instance`.
    if service_name in _local_services:
        func = _local_services[service_name]
        # We pass *args directly. They are likely Any() objects.
        return func(*args)
    else:
        # If we found the name in Rust but not in local memory, it implies 
        # the service is on another node. In this PoC, we only have one process context 
        # active at a time usually, or we are simulating everything locally.
        # If we can't find it locally, we can't run it in this PoC.
        raise RuntimeError(f"Service '{service_name}' found in registry but code not available locally.")
        
