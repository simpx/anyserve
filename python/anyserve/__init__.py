# KServe v2 API
try:
    from anyserve.kserve import (
        AnyServe,
        infer,
        ModelInferRequest, ModelInferResponse,
        InferInputTensor, InferOutputTensor, InferTensorContents,
        Capability, Context,
    )
except ImportError:
    from .kserve import (
        AnyServe,
        infer,
        ModelInferRequest, ModelInferResponse,
        InferInputTensor, InferOutputTensor, InferTensorContents,
        Capability, Context,
    )

__all__ = [
    "AnyServe",
    "infer",
    "ModelInferRequest", "ModelInferResponse",
    "InferInputTensor", "InferOutputTensor", "InferTensorContents",
    "Capability", "Context",
]
