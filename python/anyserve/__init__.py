# KServe v2 API
try:
    from anyserve.kserve import (
        AnyServe,
        model, infer,
        ModelInferRequest, ModelInferResponse,
        InferInputTensor, InferOutputTensor, InferTensorContents,
        Capability, Context,
    )
except ImportError:
    from .kserve import (
        AnyServe,
        model, infer,
        ModelInferRequest, ModelInferResponse,
        InferInputTensor, InferOutputTensor, InferTensorContents,
        Capability, Context,
    )

__all__ = [
    "AnyServe",
    "model", "infer",
    "ModelInferRequest", "ModelInferResponse",
    "InferInputTensor", "InferOutputTensor", "InferTensorContents",
    "Capability", "Context",
]
