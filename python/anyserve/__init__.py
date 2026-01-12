# KServe v2 API (standalone, no C++ dependencies)
try:
    from anyserve.kserve import (
        AnyServe,
        model, infer,
        ModelInferRequest, ModelInferResponse,
        InferInputTensor, InferOutputTensor, InferTensorContents
    )
except ImportError:
    from .kserve import (
        AnyServe,
        model, infer,
        ModelInferRequest, ModelInferResponse,
        InferInputTensor, InferOutputTensor, InferTensorContents
    )

# Core API (requires C++ extension)
try:
    from anyserve.api import init, service, capability, call, register_upgrade, DelegationError
    from anyserve.objects import Any
    from . import _core
except ImportError as e:
    # C++ extension not available - only KServe API will work
    init = None
    service = None
    capability = None
    call = None
    register_upgrade = None
    DelegationError = None
    Any = None
    _core = None

__all__ = [
    # KServe v2 API (always available)
    "AnyServe",
    "model", "infer",
    "ModelInferRequest", "ModelInferResponse",
    "InferInputTensor", "InferOutputTensor", "InferTensorContents",
    # Core API (requires C++ extension)
    "init", "service", "capability", "call", "register_upgrade", "DelegationError", "Any", "_core",
]
