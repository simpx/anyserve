# AI Agent Guide - AnyServe

## 1. Project Architecture (项目架构)
这是一个混合语言项目，旨在结合 Python 的生态易用性和 Rust 的极致性能。

- **Frontend / Control Plane (Python)**:
    - 负责 API 定义、请求处理、业务编排。
    - 使用 `FastAPI` 框架。
    - 代码位于 `python/anyserve/`。
- **Backend / Data Plane (Rust)**:
    - 负责 CPU 密集型计算、核心逻辑、低延迟任务。
    - 通过 `PyO3` 暴露给 Python。
    - 代码位于 `src/` (Rust lib) 和 `Cargo.toml`。
- **Bridge (Maturin)**:
    - 构建工具，负责编译 Rust 代码并将其打包为 Python 扩展模块 (`_core`)。

## 2. Development Workflow (开发流程)
AI Agent 在执行任务时应遵循以下工作流：

1.  **Modify Rust**: 如果涉及到性能敏感或核心逻辑修改，优先编辑 `src/lib.rs`。
2.  **Expose to Python**: 确保新的 Rust 函数通过 `#[pyfunction]` 和 `m.add_function` 暴露。
3.  **Compile**: 运行 `just build` (或 `uv run maturin develop`) 来重新编译 Rust 扩展并更新 Python 环境。
4.  **Update Python**: 在 `python/anyserve/` 中使用新的 Rust 逻辑。
5.  **Run**: 运行 `just run` 启动服务。

## 3. Code Standards (代码规范)
- **Rust**: 遵循标准 Rust 风格。使用 `Result` 处理错误。
- **Python**: 尽量使用 Type Hints。FastAPI 路由应清晰定义。
- **Naming**: Python 模块名为 `anyserve`，Rust 扩展内部名为 `_core` (在 Python 中体现为 `anyserve._core`)。

## 4. Environment (环境验证)
- 运行 `just run` 应当能启动服务器。
- 访问 `http://127.0.0.1:8000` 验证 Rust 函数调用。
