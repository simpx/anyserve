# AI Agent Guide - AnyServe

> 本文档旨在指导 AI Agent 理解项目架构、上下文与开发规范，以便高效进行代码维护与功能扩展。

## 1. Project Overview (项目概览)

**AnyServe** 是一个 **面向大规模 LLM 推理的 Capability-Oriented Serving Runtime**。
它的核心目标是为上层请求级调度器提供一个稳定的执行层，以 **capability**（语义能力）为单位进行编排，支持 **delegation**（委托）机制来处理不匹配的请求。

## 2. Architecture & Responsibilities (架构与职责)

本项目采用 **Rust (Control Plane) + Python (Execution Plane)** 的混合架构。

### 2.1 Rust Runtime (Control Plane)
> 位于 `src/`，核心控制逻辑，主进程。

- **职责**:
    - **Ingress**: 处理 gRPC/HTTP 请求入口。
    - **Dispatch**: 请求排队、并发控制、capability 路由。
    - **Delegation**: 当本地无法满足 capability 时，执行能力升级并交由调度器重路由。
    - **IPC**: 管理 Python Worker 进程，通过 IPC 传递请求与结果。
    - **Object Plane**: 控制大对象传输与生命周期（MVP 阶段仅 Stub）。

### 2.2 Python Worker (Execution Plane)
> 位于 `python/anyserve/`，具体业务逻辑，子进程。

- **职责**:
    - **Handlers**: 用户编写的 capability 实现逻辑。
    - **Inference**: 集成推理引擎（如 vLLM, sglang, torch逻辑）。
    - **Execution**: 接收 Rust 派发的请求，执行并返回结果。

## 3. Core Concepts (核心概念)

开发时必须准确理解以下术语：

- **Capability (能力)**: 语义层面的计算能力（如 `decode`, `decode.heavy`, `embedding`），而非物理资源描述。
- **Replica (副本)**: AnyServe 的运行时单元，注册一组 capabilities。
- **Delegation (委托)**: 本地 Replica 无法满足请求 capability 时，将其升级（Upgrade）并交还调度器重新路由的机制。**不是** Replica 间的直接 RPC 调用。

## 4. Development Workflow (开发流程)

Agent 在进行开发任务时，应遵循以下标准流程：

1.  **Modify Rust (`src/`)**:
    - 涉及控制流、通信、高性能逻辑修改时。
    - 使用 `#[pyfunction]` / `#[pymethods]` 通过 PyO3 暴露接口。
2.  **Compile Bridge**:
    - 运行 `just build` (或 `uv run maturin develop`)。
    - 这会将 Rust 代码编译为 `anyserve._core` 扩展模块并安装到 Python 环境。
3.  **Modify Python (`python/anyserve/`)**:
    - 涉及具体 handler 实现、业务逻辑、接口定义时。
    - 调用 `anyserve._core` 中的 Rust 绑定。
4.  **Verify**:
    - 运行 `just run` 启动服务。
    - 运行 `just test` (如果有) 或手动测试 endpoints。

## 5. Code Standards (代码规范)

- **Rust**:
    - 遵循标准 Rust 风格，使用 `cargo fmt`。
    - 错误处理必须使用 `Result`，并通过 `PyResult` 转换为 Python 异常。
- **Python**:
    - 使用 Type Hints。
    - 模块名为 `anyserve`，Rust 扩展引用为 `from . import _core`。
- **Dependencies**:
    - Rust 依赖管理：`Cargo.toml`
    - Python 依赖/环境管理：`pyproject.toml` (使用 `uv` 管理)

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

- `just build`: 编译 Rust 并安装 Python 扩展。
- `just run`: 启动 AnyServe 服务（通常是 demo）。
- `just run-scheduler`: (如果存在) 启动模拟调度器。
