# AI Agent Guide - AnyServe

> 本文档旨在指导 AI Agent 理解项目架构、上下文与开发规范，以便高效进行代码维护与功能扩展。

## 1. Project Overview (项目概览)

**AnyServe** 是一个 **面向大规模 LLM 推理的 Capability-Oriented Serving Runtime**。
它的核心目标是为上层请求级调度器提供一个稳定的执行层，以 **capability**（语义能力）为单位进行编排，支持 **delegation**（委托）机制来处理不匹配的请求。

## 2. Architecture & Responsibilities (架构与职责)

本项目采用 **C++ (Control Plane) + Python (Execution Plane)** 的混合架构。

### 2.1 C++ Runtime (Control Plane)
> 位于 `cpp/src/`，核心控制逻辑，主进程。

- **职责**:
    - **Ingress**: 处理 gRPC 请求入口（基于 KServe v2 协议）。
    - **Dispatch**: 请求排队、并发控制、capability 路由。
    - **Delegation**: 当本地无法满足 capability 时，执行能力升级并交由调度器重路由。
    - **IPC**: 管理 Python Worker 进程，通过 Unix Domain Socket 传递请求与结果。
    - **Object Plane**: 控制大对象传输与生命周期（通过 POSIX SHM）。

- **核心组件**:
    - `anyserve_core.hpp/cpp` - 核心控制平面类
    - `shm_manager.hpp/cpp` - POSIX 共享内存管理
    - `process_supervisor.hpp/cpp` - Python Worker 进程管理
    - `python_bindings.cpp` - pybind11 绑定（暴露 `anyserve._core` 模块）
    - `main.cpp` - 独立可执行文件入口

- **异步框架**: gRPC C++ async CompletionQueue

### 2.2 Python Worker (Execution Plane)
> 位于 `python/anyserve/`，具体业务逻辑，子进程。

- **职责**:
    - **Handlers**: 用户编写的 capability 实现逻辑。
    - **Inference**: 集成推理引擎（如 vLLM, sglang, torch逻辑）。
    - **Execution**: 接收 C++ 派发的请求，执行并返回结果。

## 3. Core Concepts (核心概念)

开发时必须准确理解以下术语：

- **Capability (能力)**: 语义层面的计算能力（如 `decode`, `decode.heavy`, `embedding`），而非物理资源描述。
- **Replica (副本)**: AnyServe 的运行时单元，注册一组 capabilities。
- **Delegation (委托)**: 本地 Replica 无法满足请求 capability 时，将其升级（Upgrade）并交还调度器重新路由的机制。**不是** Replica 间的直接 RPC 调用。

## 4. Development Workflow (开发流程)

Agent 在进行开发任务时，应遵循以下标准流程：

1.  **Modify C++ (`cpp/src/`)**:
    - 涉及控制流、通信、高性能逻辑修改时。
    - 通过 pybind11 暴露接口到 Python。
2.  **Build C++ Extension**:
    - 运行 `just setup-cpp` 安装 C++ 依赖（首次或依赖变更时）。
    - 运行 `just build` 编译 C++ 并生成 `anyserve._core` Python 扩展。
3.  **Modify Python (`python/anyserve/`)**:
    - 涉及具体 handler 实现、业务逻辑、接口定义时。
    - 调用 `anyserve._core` 中的 C++ 绑定。
4.  **Verify**:
    - 运行 `just run` 启动服务。
    - 运行 `just test` 运行测试。

## 5. Code Standards (代码规范)

- **C++**:
    - C++17 标准。
    - 使用 `namespace anyserve` 包裹所有代码。
    - 错误处理使用异常，通过 pybind11 自动转换为 Python 异常。
    - 注意 GIL 管理：调用 Python 时获取 GIL，长时间 C++ 操作时释放 GIL。
- **Python**:
    - 使用 Type Hints。
    - 模块名为 `anyserve`，C++ 扩展引用为 `from . import _core` 或 `from anyserve._core import AnyserveCore`。
- **Dependencies**:
    - C++ 依赖管理：`cpp/conanfile.txt` (使用 Conan)
    - Python 依赖/环境管理：`pyproject.toml` (使用 `uv` 管理)
    - 构建系统：CMake + scikit-build-core

## 6. MVP Scope Constraints (MVP 阶段约束)

当前处于 PoC/MVP 阶段，请严格遵守以下边界（详见 `docs/mvp.md`）：

- **Delegation**: 最多允许 **1 次** delegation（防止转发风暴）。
- **Routing**: 跨 Replica 交互必须通过 **调度器重路由**，禁止 Replica 直连。
- **Non-Goals (本阶段不做)**:
    - 复杂的 batching 策略。
    - 真实的 Object Store（目前仅内存/Stub）。
    - 复杂的 K8s 集成或 Autoscaling。
    - 多机 TP/EP 细节。

## 7. Useful Commands (常用命令)

- `just setup`: 安装 Python 依赖。
- `just setup-cpp`: 安装 C++ 依赖（Conan）。
- `just build`: 编译 C++ 并安装 Python 扩展。
- `just build-node`: 仅编译独立可执行文件。
- `just run`: 启动 AnyServe 服务。
- `just run-node <target>`: 启动独立 node 并加载指定 app。
- `just test`: 运行测试。
- `just clean`: 清理构建产物。
- `just gen-proto`: 生成 proto 文件。

## 8. Directory Structure (目录结构)

```
anyserve/
├── cpp/                    # C++ 控制平面
│   ├── CMakeLists.txt      # CMake 构建配置
│   ├── conanfile.txt       # Conan 依赖配置
│   └── src/
│       ├── anyserve_core.hpp/cpp    # 核心控制平面
│       ├── shm_manager.hpp/cpp      # SHM 管理
│       ├── process_supervisor.hpp/cpp # 进程管理
│       ├── python_bindings.cpp      # pybind11 绑定
│       └── main.cpp                 # 独立可执行入口
├── python/
│   └── anyserve/           # Python 包
│       ├── __init__.py
│       ├── api.py          # 用户 API
│       ├── core.py         # 核心封装（调用 _core）
│       └── _core.so        # C++ 扩展（编译生成）
├── proto/                  # gRPC proto 定义
├── anyserve_worker/        # Python Worker 实现
├── anyserve_scheduler/     # 调度器（PoC）
├── examples/               # 示例代码
├── docs/                   # 文档
├── pyproject.toml          # Python 项目配置
└── Justfile                # 构建命令
