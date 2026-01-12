from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class RegisterModelRequest(_message.Message):
    __slots__ = ("model_name", "model_version", "worker_address", "worker_id")
    MODEL_NAME_FIELD_NUMBER: _ClassVar[int]
    MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    WORKER_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    model_name: str
    model_version: str
    worker_address: str
    worker_id: str
    def __init__(self, model_name: _Optional[str] = ..., model_version: _Optional[str] = ..., worker_address: _Optional[str] = ..., worker_id: _Optional[str] = ...) -> None: ...

class RegisterModelResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class UnregisterModelRequest(_message.Message):
    __slots__ = ("model_name", "model_version", "worker_id")
    MODEL_NAME_FIELD_NUMBER: _ClassVar[int]
    MODEL_VERSION_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    model_name: str
    model_version: str
    worker_id: str
    def __init__(self, model_name: _Optional[str] = ..., model_version: _Optional[str] = ..., worker_id: _Optional[str] = ...) -> None: ...

class UnregisterModelResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class HeartbeatRequest(_message.Message):
    __slots__ = ("worker_id", "model_names")
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    MODEL_NAMES_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    model_names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, worker_id: _Optional[str] = ..., model_names: _Optional[_Iterable[str]] = ...) -> None: ...

class HeartbeatResponse(_message.Message):
    __slots__ = ("healthy",)
    HEALTHY_FIELD_NUMBER: _ClassVar[int]
    healthy: bool
    def __init__(self, healthy: bool = ...) -> None: ...
