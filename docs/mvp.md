# anyServe MVP Step 1: Core Skeleton & Simulation

本文档定义了 anyServe 项目的第一阶段（Step 1）实施细则。
目标是构建一个 **最小可运行的骨架（Minimum Runnable Skeleton）**，验证 Rust Control Plane、Python Execution Plane、Delegation 机制以及模拟的 Object 系统。

---

## 1. 核心目标 (Objectives)

在 **单机环境** 下，通过 **多进程** 模拟分布式架构，跑通以下核心链路：

1.  **Request Lifecycle**: Client -> gRPC (Rust) -> Python Worker -> Response.
2.  **Delegation**: 当请求的 Capability 本地不满足时，自动转发到正确节点。
3.  **Simulation**: 模拟 Object Store 和 Inference Engine，不引入外部重依赖。

---

## 2. 架构简化 (Simplifications for Step 1)

为了快速跑通核心逻辑，我们对部分组件进行“模拟”或简化实现：

### 2.1 基础设施模拟 (Infrastructure)
使用 **单机多端口** 模拟集群：
- **Scheduler**: Python HTTP Service (localhost:8000)
- **Node A (Standard)**: Rust Runtime (localhost:50051)
- **Node B (Heavy)**: Rust Runtime (localhost:50052)
- **Client**: Python script

### 2.2 Object System (简化版)
- **实现**: 基于 **本地文件系统 (Local FS)**。
- **机制**: 
    - 既然是单机多进程模拟，所有节点共享一个目录（如 `/tmp/anyserve_data`）。
    - `ObjRef` 本质是一个 UUID 或文件路径字符串。
    - **Rust** 负责生成 UUID。
    - **Python** 负责将数据写入文件或从文件读取。
- **目的**: 验证“控制流（Control Flow）与数据流（Data Flow）分离”的接口设计，即 gRPC 传递 Reference，Worker 读写 File。

### 2.3 Inference Engine (模拟版)
- **实现**: 纯 Python 函数，不依赖 pytorch/vLLM。
- **功能**:
    - `generate(text)`: 模拟推理，`time.sleep(1)`，返回反转字符串或追加文本。
    - **模拟 "Switching" (切换)**: Worker 内部维护一个 `current_model` 状态。如果请求的 capability 需要的模型与当前不同，执行一个 `mock_load_model()` (sleep 2s)，模拟上下文切换开销。

### 2.4 Scheduler (模拟版)
- **实现**: 简单的 Python Web Server (FastAPI/Flask 甚至 `http.server`)。
- **职责**:
    - 维护全局 `ServiceRegistry` (Dict: `Capability -> [Endpoint]`)。
    - 提供 HTTP API 供 Rust Runtime 查询路由。

---

## 3. 组件设计与交互 (Component Design)

### 3.1 协议层 (Protocol)
必须使用 **gRPC** 定义 Rust Runtime 的对外接口 (`anyserve.proto`)：

```protobuf
service AnyServe {
  // 核心推理接口
  rpc Infer (InferRequest) returns (InferResponse);
}

message InferRequest {
  string capability = 1;      // e.g., "chat", "upscale"
  bytes inputs = 2;           // 简单起见，直接传 bytes 或者 json string
  repeated string input_refs = 3; // 关联的 Object IDs
}

message InferResponse {
  bytes output = 1;
  repeated string output_refs = 2;
  bool delegated = 3;         // 标识该请求是否经过了 Delegation (Debug用)
}
```

### 3.2 Rust Runtime (Control Plane)
- **Ingress**: 启动 gRPC Server。
- **Worker Management**: 
    - 启动时通过 `Command` 启动 Python 子进程。
    - 维持与 Python 的 **Standard Stdio** 或者 **Unix Domain Socket** 通信（Step 1 建议用 Stdio 简单模拟 IPC）。
- **Logic**:
    1. 接到 gRPC 请求。
    2. 检查 `req.capability` 是否在本地 `supported_capabilities` 列表中。
    3. **Case A (Match)**: 序列化请求 -> 发送给 Python Worker -> 等待结果 -> 返回 gRPC。
    4. **Case B (Mismatch)**: 
        - 请求 Scheduler (`GET /lookup?cap=xxx`) 获取目标地址。
        - 建立 gRPC Client 连接目标地址 (Simulate Delegation Proxy)。
        - 转发请求并返回结果。

### 3.3 Python Worker (Execution Plane)
- 独立进程，被 Rust 拉起。
- 循环读取指令（from Stdin/Socket）。
- 逻辑：
    ```python
    while True:
        req = read_request()
        if req.op == "infer":
             # 模拟 Load Model
             if req.cap != self.current_cap:
                 time.sleep(2) # switching cost
                 self.current_cap = req.cap
             
             # 模拟 Inference
             result = mock_engine(req.input)
             
             # 模拟 Large Object Output
             if len(result) > threshold:
                 path = save_to_fs(result)
                 write_response(ref=path)
             else:
                 write_response(data=result)
    ```

---

## 4. 演示场景 (Demo Scenario)

编写 `examples/demo_step1.py` 脚本，按顺序执行：

1. **环境准备**: 清理/创建 `/tmp/anyserve_data`。
2. **启动组件**:
    - 启动 Scheduler (Port 8000).
    - 启动 Node A (Port 50051, Caps=["small"]).
    - 启动 Node B (Port 50052, Caps=["large"]).
3. **测试 Local Hit**:
    - Client -> Node A ("small") -> 成功 (Fast).
4. **测试 Delegation**:
    - Client -> Node A ("large") -> Node A 查 Scheduler -> Forward Node B -> 成功 (Slightly Slower).
5. **测试 Object Ref**:
    - Client -> Node B ("large", input="make_huge_data") -> 返回一个文件路径 Ref -> Client 读取文件验证内容。

---

## 5. 开发顺序建议

1. **Proto Definition**: 定义 `.proto` 文件。
2. **Scheduler**: 写个最简单的 FastAPI app。
3. **Python Worker**: 写一个能从 Stdin 读 JSON 并 echo 的脚本。
4. **Rust Runtime**: 
    - 实现 gRPC basic server。
    - 实现 `Command::new("python").spawn()` 并在 Rust 里写数据给 Python。
5. **Integration**: 串联 gRPC 到 Python 的通路。
6. **Delegation**: 添加 HTTP Client 调用 Scheduler 和 gRPC Client 转发逻辑。
