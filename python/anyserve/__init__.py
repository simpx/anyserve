__version__ = "0.1.2"

# KServe v2 API
try:
    from anyserve.kserve import (
        AnyServe,
        infer,
        ModelInferRequest, ModelInferResponse,
        InferInputTensor, InferOutputTensor, InferTensorContents,
        Capability, Context, Stream,
    )
except ImportError:
    from .kserve import (
        AnyServe,
        infer,
        ModelInferRequest, ModelInferResponse,
        InferInputTensor, InferOutputTensor, InferTensorContents,
        Capability, Context, Stream,
    )

__all__ = [
    "AnyServe",
    "infer",
    "ModelInferRequest", "ModelInferResponse",
    "InferInputTensor", "InferOutputTensor", "InferTensorContents",
    "Capability", "Context", "Stream",
]
