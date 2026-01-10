import random
import functools
import pickle
import base64
import urllib.request
import json
from typing import Callable, Any as PyAny
from anyserve.core import get_core, init as core_init
from anyserve.objects import Any
import anyserve.http_server as http_server

# Global registry for local function implementations
_local_services = {}

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
    core, http_port = core_init(root_dir, instance_id, port)
    
    # Start Control Plane
    http_server.start_background_server("0.0.0.0", http_port, _local_services)
    
    _register_all_local_services()
    return core

def _remote_call(target_address, service_name, args):
    """Perform HTTP POST to remote control plane."""
    url = f"http://{target_address}/call/{service_name}"
    
    # Serialize args using pickle then base64
    args_bytes = pickle.dumps(args)
    args_b64 = base64.b64encode(args_bytes).decode('utf-8')
    
    payload = {
        "args_pickle_b64": args_b64
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    with urllib.request.urlopen(req) as response:
        resp_data = json.loads(response.read().decode('utf-8'))
        
    if resp_data.get("status") != "ok":
        raise RuntimeError(f"Remote call failed: {resp_data.get('error')}")
        
    result_b64 = resp_data["result_pickle_b64"]
    result_bytes = base64.b64decode(result_b64)
    return pickle.loads(result_bytes)

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
    target_address = random.choice(instances) # IP:HTTP_PORT
    
    # 3. Execution (RPC)
    # Check if local optimization (optional)
    # But for strict distributed demo, we can just always use network or check if target is us.
    # checking if target_addr in my_addrs?
    # Simple: Just call remote.
    
    return _remote_call(target_address, service_name, args)
