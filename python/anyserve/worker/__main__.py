#!/usr/bin/env python3
"""
AnyServe Worker - 独立 Worker 进程

Worker 负责:
1. 加载用户定义的模型处理函数
2. 启动 Unix Socket 服务器
3. 接收来自 C++ Ingress 的请求
4. 调用对应的模型处理函数
5. 返回响应给 Ingress
6. 向 API Server 注册 capabilities (MVP)
7. 启动 gRPC server 处理流式请求 (MVP Phase 7)
"""

import sys
import os
import socket
import struct
import argparse
import importlib
import signal
import httpx
import threading
from typing import Dict, Tuple, Callable, Optional, List, Any
from concurrent import futures

# 导入模型类型
from anyserve.kserve import ModelInferRequest, ModelInferResponse, Context, Capability, Stream


def main():
    parser = argparse.ArgumentParser(description='AnyServe Worker')
    parser.add_argument('--app', required=True, help='Application (module:app)')
    parser.add_argument('--ingress', required=True, help='Ingress address (host:port)')
    parser.add_argument('--worker-id', required=True, help='Worker ID')
    parser.add_argument('--worker-port', type=int, default=None, help='Worker port for Unix socket')
    parser.add_argument('--api-server', default=None, help='API Server URL (e.g., http://localhost:8080)')
    parser.add_argument('--object-store', default='/tmp/anyserve-objects', help='Object store path')
    parser.add_argument('--replica-id', default=None, help='Replica ID for registration')
    parser.add_argument('--grpc-port', type=int, default=None, help='gRPC port for streaming (default: ingress_port + 100)')
    parser.add_argument('--factory', action='store_true', help='Treat app as factory function')

    args = parser.parse_args()

    # 1. 加载应用
    module_path, app_name = args.app.split(":")
    module = importlib.import_module(module_path)

    if args.factory:
        # Factory 模式：调用函数获取 app
        factory_func = getattr(module, app_name)
        app = factory_func()
    else:
        # 普通模式：直接获取 app 对象
        app = getattr(module, app_name)

    # Determine gRPC port for streaming
    ingress_port = int(args.ingress.split(":")[1])
    grpc_port = args.grpc_port or (ingress_port + 100)

    # 2. 创建 Worker
    worker = Worker(
        app=app,
        worker_id=args.worker_id,
        ingress_address=args.ingress,
        worker_port=args.worker_port,
        api_server=args.api_server,
        object_store_path=args.object_store,
        replica_id=args.replica_id or args.worker_id,
        grpc_port=grpc_port,
    )

    # 3. 向 Ingress 注册
    worker.register_to_ingress()

    # 4. 向 API Server 注册 (如果配置了)
    if args.api_server:
        worker.register_to_api_server()

    # 5. 启动 gRPC server (for streaming) 和 Unix Socket 服务器
    worker.serve()


class Worker:
    """Worker 进程 - 处理推理请求"""

    def __init__(
        self,
        app,
        worker_id: str,
        ingress_address: str,
        worker_port: int = None,
        api_server: str = None,
        object_store_path: str = '/tmp/anyserve-objects',
        replica_id: str = None,
        grpc_port: int = None,
    ):
        self.app = app
        self.worker_id = worker_id
        self.ingress_address = ingress_address
        self.api_server = api_server
        self.replica_id = replica_id or worker_id
        self.grpc_port = grpc_port

        # Unix Socket 路径
        if worker_port:
            self.socket_path = f"/tmp/anyserve-worker-{worker_id}-{worker_port}.sock"
        else:
            self.socket_path = f"/tmp/anyserve-worker-{worker_id}.sock"

        self.running = True
        self.grpc_server = None

        # Initialize ObjectStore
        from anyserve.objects import ObjectStore
        self.object_store = ObjectStore(object_store_path)

        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """处理关闭信号"""
        print(f"\n[Worker-{self.worker_id}] Received signal {signum}, shutting down...")
        self.running = False

        # Unregister from API Server
        if self.api_server:
            self.unregister_from_api_server()

    def register_to_api_server(self):
        """向 API Server 注册 capabilities"""
        if not self.api_server:
            return

        # 收集 capabilities
        capabilities = []

        # 从 capability handlers 收集
        if hasattr(self.app, '_capability_handlers'):
            for cap, handler, uses_context, is_stream in self.app._capability_handlers:
                capabilities.append(cap.to_dict())

        # 从 legacy model registry 收集 (转换为 capability 格式)
        if hasattr(self.app, '_local_registry') and not capabilities:
            for (model_name, version), handler in self.app._local_registry.items():
                cap = {"type": model_name}
                if version:
                    cap["model"] = version
                capabilities.append(cap)

        if not capabilities:
            print(f"[Worker-{self.worker_id}] No capabilities to register")
            return

        # 注册到 API Server
        try:
            # Extract host and port from ingress address for gRPC endpoint
            ingress_host, ingress_port = self.ingress_address.split(":")

            register_data = {
                "replica_id": self.replica_id,
                "endpoint": f"localhost:{ingress_port}",  # gRPC endpoint
                "capabilities": capabilities,
            }

            print(f"[Worker-{self.worker_id}] Registering to API Server: {self.api_server}")
            print(f"[Worker-{self.worker_id}] Capabilities: {capabilities}")

            response = httpx.post(
                f"{self.api_server}/register",
                json=register_data,
                timeout=10.0,
            )

            if response.status_code == 200:
                result = response.json()
                print(f"[Worker-{self.worker_id}] API Server registration: {result['message']}")
            else:
                print(f"[Worker-{self.worker_id}] API Server registration failed: {response.status_code}")

        except Exception as e:
            print(f"[Worker-{self.worker_id}] Failed to register with API Server: {e}")

    def unregister_from_api_server(self):
        """从 API Server 注销"""
        if not self.api_server:
            return

        try:
            response = httpx.request(
                "DELETE",
                f"{self.api_server}/unregister",
                json={"replica_id": self.replica_id},
                timeout=5.0,
            )
            if response.status_code == 200:
                print(f"[Worker-{self.worker_id}] Unregistered from API Server")
        except Exception as e:
            print(f"[Worker-{self.worker_id}] Failed to unregister: {e}")

    def register_to_ingress(self):
        """向 Ingress 注册所有模型"""
        # 检查 app 是否有 _local_registry
        if not hasattr(self.app, '_local_registry') or not self.app._local_registry:
            print(f"[Worker-{self.worker_id}] Warning: No models registered in app")
            return

        print(f"[Worker-{self.worker_id}] Found {len(self.app._local_registry)} registered models")

        # 导入 worker management protobuf
        try:
            import grpc
            import sys
            import os
            # Add _proto directory to path
            proto_path = os.path.join(os.path.dirname(__file__), '..', '_proto')
            if proto_path not in sys.path:
                sys.path.insert(0, proto_path)

            from anyserve._proto import worker_management_pb2_grpc
            from anyserve._proto import worker_management_pb2

            print(f"[Worker-{self.worker_id}] Connecting to Ingress at {self.ingress_address}")

            # 创建 gRPC channel
            channel = grpc.insecure_channel(self.ingress_address)
            stub = worker_management_pb2_grpc.WorkerManagementStub(channel)

            # 遍历所有注册的模型并注册
            worker_address = f"unix://{self.socket_path}"

            for (model_name, version), handler in self.app._local_registry.items():
                request = worker_management_pb2.RegisterModelRequest(
                    model_name=model_name,
                    model_version=version or "",
                    worker_address=worker_address,
                    worker_id=self.worker_id
                )

                try:
                    response = stub.RegisterModel(request, timeout=5.0)
                    if response.success:
                        print(f"[Worker-{self.worker_id}] Registered model: {model_name}" +
                              (f":{version}" if version else ""))
                    else:
                        print(f"[Worker-{self.worker_id}] Failed to register {model_name}: {response.message}")
                except grpc.RpcError as e:
                    print(f"[Worker-{self.worker_id}] gRPC error registering {model_name}: {e.code()} - {e.details()}")

            channel.close()
            print(f"[Worker-{self.worker_id}] Model registration completed")

        except ImportError as e:
            print(f"[Worker-{self.worker_id}] Warning: grpc not available, skipping registration: {e}")
            # 继续运行，即使注册失败
        except Exception as e:
            print(f"[Worker-{self.worker_id}] Failed to register models: {e}")
            import traceback
            traceback.print_exc()
            # 不抛出异常，允许 Worker 继续运行

    def serve(self):
        """启动 gRPC server 和 Unix Socket 服务器"""
        # 启动 gRPC server (for streaming) 在后台线程
        if self.grpc_port:
            self._start_grpc_server()

        # 删除旧 socket 文件
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        # 创建 Unix Socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(self.socket_path)
        sock.listen(5)
        sock.settimeout(1.0)  # 设置超时以便能响应关闭信号

        print(f"[Worker-{self.worker_id}] Listening on {self.socket_path}")

        try:
            while self.running:
                try:
                    conn, _ = sock.accept()
                    self.handle_connection(conn)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[Worker-{self.worker_id}] Accept error: {e}")
        except KeyboardInterrupt:
            print(f"\n[Worker-{self.worker_id}] Shutting down...")
        finally:
            sock.close()
            if os.path.exists(self.socket_path):
                os.remove(self.socket_path)
            self._stop_grpc_server()
            print(f"[Worker-{self.worker_id}] Stopped")

    def _start_grpc_server(self):
        """启动 gRPC server 处理流式请求"""
        try:
            import grpc
            from anyserve._proto import grpc_predict_v2_pb2_grpc, grpc_predict_v2_pb2

            # Create gRPC server
            self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

            # Add servicer
            servicer = StreamingServicer(self)
            grpc_predict_v2_pb2_grpc.add_GRPCInferenceServiceServicer_to_server(
                servicer, self.grpc_server
            )

            # Bind to port
            self.grpc_server.add_insecure_port(f'[::]:{self.grpc_port}')
            self.grpc_server.start()

            print(f"[Worker-{self.worker_id}] gRPC streaming server started on port {self.grpc_port}")

        except Exception as e:
            print(f"[Worker-{self.worker_id}] Failed to start gRPC server: {e}")
            import traceback
            traceback.print_exc()

    def _stop_grpc_server(self):
        """停止 gRPC server"""
        if self.grpc_server:
            self.grpc_server.stop(grace=5)
            print(f"[Worker-{self.worker_id}] gRPC server stopped")

    def handle_connection(self, conn: socket.socket):
        """处理单个连接"""
        try:
            # 读取请求长度（4 bytes, big-endian）
            length_bytes = conn.recv(4)
            if not length_bytes:
                return

            request_length = struct.unpack("!I", length_bytes)[0]

            # 读取请求数据
            request_data = b""
            while len(request_data) < request_length:
                chunk = conn.recv(min(4096, request_length - len(request_data)))
                if not chunk:
                    break
                request_data += chunk

            # 解析 protobuf 请求
            from anyserve.kserve import _proto_to_python_request, _python_to_proto_response
            request = _proto_to_python_request(request_data)

            # 调用模型处理函数
            response = self.dispatch_request(request)

            # 序列化响应
            response_data = _python_to_proto_response(response)

            # 发送响应长度 + 数据
            response_length = len(response_data)
            conn.sendall(struct.pack("!I", response_length))
            conn.sendall(response_data)

        except Exception as e:
            print(f"[Worker-{self.worker_id}] Error handling request: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()

    def _create_context(self, capability: Optional[Capability] = None) -> Context:
        """创建 Context 对象"""
        return Context(
            objects=self.object_store,
            api_server=self.api_server,
            replica_id=self.replica_id,
            capability=capability,
        )

    def dispatch_request(self, request: ModelInferRequest) -> ModelInferResponse:
        """分发请求到对应的模型处理函数"""
        model_name = request.model_name
        model_version = request.model_version

        handler = None
        uses_context = False
        matched_capability = None

        # 1. 尝试 capability 匹配 (优先)
        if hasattr(self.app, '_capability_handlers'):
            capability_query = {"type": model_name}
            if model_version:
                capability_query["model"] = model_version

            result = self.app.find_handler(capability_query)
            if result:
                handler, uses_context, matched_capability = result

        # 2. 尝试精确匹配（name + version）
        if handler is None and hasattr(self.app, '_local_registry'):
            if (model_name, model_version) in self.app._local_registry:
                handler = self.app._local_registry[(model_name, model_version)]

            # 3. 尝试无版本匹配
            elif (model_name, None) in self.app._local_registry:
                handler = self.app._local_registry[(model_name, None)]

            # 4. 尝试空版本字符串匹配
            elif model_version and (model_name, "") in self.app._local_registry:
                handler = self.app._local_registry[(model_name, "")]

        if handler is None:
            # 返回错误响应
            return ModelInferResponse(
                model_name=model_name,
                model_version=model_version or "",
                outputs=[],
                error=f"Model '{model_name}' not found in this worker"
            )

        # 调用处理函数
        try:
            if uses_context:
                # New capability-style handler with context
                context = self._create_context(matched_capability)
                response = handler(request, context)
            else:
                # Legacy model-style handler without context
                response = handler(request)
            return response
        except Exception as e:
            import traceback
            error_msg = f"Error in model handler: {str(e)}\n{traceback.format_exc()}"
            print(f"[Worker-{self.worker_id}] {error_msg}")

            return ModelInferResponse(
                model_name=model_name,
                model_version=model_version or "",
                outputs=[],
                error=error_msg
            )

    def dispatch_stream_request(self, proto_request, grpc_context):
        """分发流式请求到对应的流式处理函数"""
        from anyserve._proto import grpc_predict_v2_pb2
        from anyserve.kserve import _proto_to_python_request

        model_name = proto_request.model_name
        model_version = proto_request.model_version

        # 查找流式 handler
        if not hasattr(self.app, 'find_stream_handler'):
            yield grpc_predict_v2_pb2.ModelStreamInferResponse(
                error_message=f"Streaming not supported"
            )
            return

        capability_query = {"type": model_name}
        if model_version:
            capability_query["model"] = model_version

        result = self.app.find_stream_handler(capability_query)
        if not result:
            yield grpc_predict_v2_pb2.ModelStreamInferResponse(
                error_message=f"No streaming handler for capability: {capability_query}"
            )
            return

        handler, uses_context, matched_capability = result

        # Convert proto request to Python request
        py_request = _proto_to_python_request(proto_request.SerializeToString())

        # 创建 Stream 对象
        stream = Stream()

        # 创建 Context
        context = self._create_context(matched_capability)

        # 在后台线程中运行 handler
        def run_handler():
            try:
                handler(py_request, context, stream)
            except Exception as e:
                import traceback
                error_msg = f"Error in stream handler: {str(e)}\n{traceback.format_exc()}"
                print(f"[Worker-{self.worker_id}] {error_msg}")
                stream.error(error_msg)
            finally:
                if not stream._closed:
                    stream.close()

        handler_thread = threading.Thread(target=run_handler)
        handler_thread.start()

        # 从 Stream 中读取响应并 yield
        for response in stream.iter_responses():
            if isinstance(response, dict) and "error_message" in response:
                yield grpc_predict_v2_pb2.ModelStreamInferResponse(
                    error_message=response["error_message"]
                )
            else:
                # response 应该是 ModelStreamInferResponse proto
                yield response

        handler_thread.join(timeout=5.0)


class StreamingServicer:
    """gRPC servicer 用于处理流式请求"""

    def __init__(self, worker: Worker):
        self.worker = worker

    def ModelStreamInfer(self, request, context):
        """处理流式推理请求"""
        yield from self.worker.dispatch_stream_request(request, context)

    # 实现其他必需的 RPC 方法（转发到非流式处理）
    def ServerLive(self, request, context):
        from anyserve._proto import grpc_predict_v2_pb2
        return grpc_predict_v2_pb2.ServerLiveResponse(live=True)

    def ServerReady(self, request, context):
        from anyserve._proto import grpc_predict_v2_pb2
        return grpc_predict_v2_pb2.ServerReadyResponse(ready=True)

    def ModelReady(self, request, context):
        from anyserve._proto import grpc_predict_v2_pb2
        return grpc_predict_v2_pb2.ModelReadyResponse(ready=True)

    def ServerMetadata(self, request, context):
        from anyserve._proto import grpc_predict_v2_pb2
        return grpc_predict_v2_pb2.ServerMetadataResponse(
            name="anyserve",
            version="0.1.0",
        )

    def ModelMetadata(self, request, context):
        from anyserve._proto import grpc_predict_v2_pb2
        return grpc_predict_v2_pb2.ModelMetadataResponse(
            name=request.name,
        )

    def ModelInfer(self, request, context):
        """处理非流式推理请求（转发到 Worker）"""
        from anyserve.kserve import _proto_to_python_request, _python_to_proto_response
        from anyserve._proto import grpc_predict_v2_pb2

        # 转换 proto request 到 Python request
        py_request = _proto_to_python_request(request.SerializeToString())

        # 调用 dispatch
        py_response = self.worker.dispatch_request(py_request)

        # 转换回 proto response
        response_bytes = _python_to_proto_response(py_response)
        response = grpc_predict_v2_pb2.ModelInferResponse()
        response.ParseFromString(response_bytes)

        return response


if __name__ == "__main__":
    main()
