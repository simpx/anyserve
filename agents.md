# AI Agent Guide - anyserve

> 本项目处于 POC 阶段，请先阅读架构文档了解设计。

## 核心文档

请按以下顺序阅读：

1. **[docs/architecture.md](docs/architecture.md)** - 架构设计（概念、原则、分层）
2. **[docs/runtime.md](docs/runtime.md)** - 运行时实现（代码结构、协议、流程）
3. **[docs/mvp.md](docs/mvp.md)** - MVP 目标和开发计划

## 快速上下文

- **项目定位**：面向 LLM 推理的 Serving Runtime
- **核心架构**：C++ Dispatcher + Python Worker
- **关键概念**：Capability（任意 key-value）、Replica、Worker 动态启停、Object System

## 开发命令

```bash
# 构建
just setup    # 安装依赖
just build    # 编译 C++
just clean    # 清理

# 运行
python -m anyserve.cli examples.basic.app:app --port 8000 --workers 1

# 测试
python examples/basic/run_example.py
```

## 代码规范

- **C++**：C++17，命名空间 `anyserve`，Google Style
- **Python**：类型注解，PEP 8
- **Commit**：`type(scope): message`，类型包括 feat/fix/refactor/docs/test/chore

## 当前状态

参见 [docs/mvp.md](docs/mvp.md) 第 5 节"当前代码状态"。
