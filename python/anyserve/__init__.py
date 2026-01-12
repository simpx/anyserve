try:
    from anyserve.api import init, service, capability, call, register_upgrade, DelegationError
    from anyserve.objects import Any
except ImportError:
    # Fallback for relative imports during development
    from .api import init, service, capability, call, register_upgrade, DelegationError
    from .objects import Any

# Import C++ core extension
try:
    from . import _core
except ImportError:
    _core = None

__all__ = ["init", "service", "capability", "call", "register_upgrade", "DelegationError", "Any", "_core"]
