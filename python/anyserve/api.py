import random
import functools
import pickle
from typing import Callable, Any as PyAny, List, Optional
from anyserve.core import get_core, init as core_init
from anyserve.objects import Any

# Global registry for local capability handlers
_local_capabilities = {}
# Global registry for capability upgrade rules (for delegation)
_capability_upgrades = {}

class DelegationError(Exception):
    """Raised when delegation is needed but not possible."""
    pass

class Dispatcher:
    def dispatch(self, capability: str, args_pickle: bytes, is_delegated: bool = False) -> bytes:
        """
        Dispatch a capability request.
        
        1. If capability is registered locally, execute it
        2. If not local but delegation is allowed, upgrade capability and delegate
        3. Otherwise, raise an error
        """
        # Check if we can serve this capability locally
        if capability in _local_capabilities:
            func = _local_capabilities[capability]
            try:
                # Deserialize
                args = pickle.loads(args_pickle)
                if not isinstance(args, (list, tuple)):
                    args = (args,)
                
                # Execute locally
                result = func(*args)
                
                # Serialize
                return pickle.dumps(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise RuntimeError(f"Execution failed: {str(e)}")
        
        # Cannot serve locally - need to delegate
        if is_delegated:
            # Already delegated once, cannot delegate again (prevent recursive delegation)
            raise RuntimeError(f"Capability '{capability}' not found locally and already delegated. Max 1 delegation allowed.")
        
        # Try to upgrade capability and delegate
        upgraded_capability = _get_upgraded_capability(capability)
        if upgraded_capability is None:
            raise RuntimeError(f"Capability '{capability}' not found locally and no upgrade path available.")
        
        print(f"[Delegation] Upgrading capability: {capability} -> {upgraded_capability}")
        
        # Delegate via scheduler re-routing
        core = get_core()
        endpoints = core.lookup_capability(upgraded_capability)
        if not endpoints:
            raise RuntimeError(f"No replicas found for upgraded capability '{upgraded_capability}'")
        
        target_address = random.choice(endpoints)
        print(f"[Delegation] Routing to: {target_address}")
        
        # Remote call with is_delegated=True to prevent further delegation
        result_pickle = core.remote_call(target_address, upgraded_capability, args_pickle, True)
        return bytes(result_pickle)

def _get_upgraded_capability(capability: str) -> Optional[str]:
    """
    Get the upgraded version of a capability.
    For MVP: decode -> decode.heavy
    """
    if capability in _capability_upgrades:
        return _capability_upgrades[capability]
    return None

def capability(name: str, upgrades_to: Optional[str] = None):
    """
    Decorator to register a capability handler.
    
    Args:
        name: The capability name (e.g., 'decode', 'decode.heavy')
        upgrades_to: If this replica cannot serve requests for this capability,
                     it will try to upgrade to this capability and delegate.
    """
    def decorator(func: Callable):
        _local_capabilities[name] = func
        if upgrades_to:
            _capability_upgrades[name] = upgrades_to
        return func
    return decorator

# Keep 'service' as an alias for backward compatibility
def service(name: str):
    """
    Decorator to register a service (backward compatible alias for capability).
    """
    return capability(name)

def _register_all_local_capabilities():
    """Helper to register all decorated capabilities to the scheduler."""
    core = get_core()
    for name in _local_capabilities:
        core.register_capability(name)
        print(f"[Anyserve] Registered capability: {name}")

# Wrap core_init to also register capabilities
def init(root_dir: str = "./tmp_anyserve", instance_id: str = None, port: int = 0, capabilities: List[str] = None):
    """
    Initialize the anyserve runtime.
    
    Args:
        root_dir: Root directory for storage
        instance_id: Unique identifier for this replica
        port: gRPC server port (0 = random)
        capabilities: List of capabilities this replica provides
    """
    dispatcher = Dispatcher()
    core = core_init(dispatcher, root_dir, instance_id, port)
    _register_all_local_capabilities()
    return core

def call(capability_name: str, *args, is_delegated: bool = False):
    """
    Call a capability by name.
    
    This will:
    1. Look up replicas that can serve this capability
    2. Route to one of them (random load balancing)
    3. Execute the capability and return the result
    """
    core = get_core()
    
    # 1. Capability Discovery via Scheduler
    endpoints = core.lookup_capability(capability_name)
    if not endpoints:
        raise RuntimeError(f"Capability '{capability_name}' not found")
    
    # 2. Load Balancing (Random for MVP)
    target_address = random.choice(endpoints)
    
    # 3. Check if local execution is possible
    if target_address == core.get_address():
        # Execute locally
        if capability_name in _local_capabilities:
            return _local_capabilities[capability_name](*args)

    # 4. Remote Call
    args_pickle = pickle.dumps(args)
    result_pickle = core.remote_call(target_address, capability_name, args_pickle, is_delegated)
    return pickle.loads(bytes(result_pickle))

def register_upgrade(from_capability: str, to_capability: str):
    """
    Register a capability upgrade path for delegation.
    
    When a request for 'from_capability' cannot be served locally,
    the runtime will upgrade it to 'to_capability' and delegate.
    """
    _capability_upgrades[from_capability] = to_capability
