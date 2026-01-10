# AnyServe

面向大规模 LLM 推理的 Capability-Oriented Serving Runtime（PoC）。采用 Rust 控制路径 + Python 执行路径的混合架构，用最小实现验证 capability 路由与委托机制。

## 文档

- [架构总览](docs/architecture.md)：三层边界、核心抽象、委托与 Object Plane。
- [MVP 范围](docs/mvp.md)：PoC 目标、非目标、验收标准。
- [agents.md](agents.md)：AI Agent 协作指南。

## 核心概念

- Capability First：以语义能力（如 decode、decode.heavy）为路由与编排单位。
- Replica as Runtime：不可拆分的执行单元（Rust runtime + Python workers），对调度器透明。
- Delegation：本地硬不匹配时升级 capability 并交由调度器重新路由，最多一次委托。

## 目录结构

- python/anyserve/：FastAPI 控制面与 Python handlers。
- src/：Rust runtime（请求接入、调度、IPC）。
- docs/：项目文档（架构与 MVP）。
- agents.md：AI Agent 协作指南。

## 快速开始

环境要求：Python 3.11+、Rust、uv、just（可选）。

1) 初始化环境（如需安装 Rust/just）：
```bash
./scripts/bootstrap.sh
```

2) 安装 Python 依赖：
```bash
uv sync
```

3) 开发模式运行：
```bash
just run
```

如需重新构建 Rust 扩展：
```bash
uv run maturin develop
```
