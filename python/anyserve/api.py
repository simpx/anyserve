import random
import functools
import pickle
from typing import Callable, Any as PyAny
from anyserve.core import get_core, init as core_init
from anyserve.objects import Any

# Global registry for local function implementations
_local_services = {}

class Dispatcher:
    def dispatch(self, service_name: str, args_pickle: bytes) -> bytes:
        if service_name not in _local_services:
            raise ValueError(f"Service {service_name} not found locally")
        
        func = _local_services[service_name]
        try:
            # Deserialize
            args = pickle.loads(args_pickle)
            if not isinstance(args, (list, tuple)):
                args = (args,)
            
            # Execute
            result = func(*args)
            
            # Serialize
            return pickle.dumps(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Execution failed: {str(e)}")

def service(name: str):
    """
    Decorator to register a service.
    """
    def decorator(func: Callable):
        _local_services[name] = func
        return func
    return decorator

def _register_all_local_services():
    """Helper to register all decorated services to the Rust NameService."""
    core = get_core()
    for name in _local_services:
        core.register_service(name)
        print(f"[Anyserve] Registered local service: {name}")

# Wrap core_init to also register services and start HTTP server
def init(root_dir: str = "./tmp_anyserve", instance_id: str = None, port: int = 0):
    dispatcher = Dispatcher()
    core = core_init(dispatcher, root_dir, instance_id, port)
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
    target_address = random.choice(instances) # IP:PORT (now unified)
    
    # 3. Execution (RPC via gRPC)
    # Check if local optimization (optional)
    if target_address == core.get_address():
       # Just run locally
       if service_name in _local_services:
           return _local_services[service_name](*args)

    # Remote Call
    args_pickle = pickle.dumps(args)
    result_pickle = core.remote_call(target_address, service_name, args_pickle)
    return pickle.loads(bytes(result_pickle))
