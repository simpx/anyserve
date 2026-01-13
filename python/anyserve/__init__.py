# KServe v2 API
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

__all__ = [
    "AnyServe",
    "model", "infer",
    "ModelInferRequest", "ModelInferResponse",
    "InferInputTensor", "InferOutputTensor", "InferTensorContents",
]
