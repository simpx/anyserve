# AI Agent Guide - anyserve

> 本项目处于 POC 阶段。

## 开始工作前

**必读文档**（按顺序）：

1. **[docs/architecture.md](docs/architecture.md)** - 架构设计（概念、原则、分层）
2. **[docs/mvp.md](docs/mvp.md)** - MVP 目标和开发计划（**重点：第 5-6 节**）
3. **[docs/runtime.md](docs/runtime.md)** - 当前运行时实现

## 当前开发任务

**按照 [docs/mvp.md](docs/mvp.md) 第 6 节的实现计划开发，从 Phase 1 开始。**

每个 Phase 包含：
- 目标
- 新建/修改的文件列表
- 具体任务列表（带 checkbox）

完成一个任务后，在 mvp.md 中将对应的 `[ ]` 改为 `[x]`。

## 快速上下文

| 概念 | 说明 |
|------|------|
| **anyserve 实例** | 部署单元，运行在一组资源上（单机或多机） |
| **Agent** | anyserve 主进程（C++），每机一个，负责流量入口、Worker 管理、请求队列、Object System |
| **Worker** | 执行推理的进程（当前 Python，未来支持 C++），1 Worker 提供 1 组 Capability |
| **Capability** | anyserve 的核心抽象，任意 key-value 数据，用于请求路由和匹配 |
| **API Server** | 独立服务，全局路由（MVP 中用 FastAPI 实现） |
| **Delegation** | 请求转发机制，当实例无法处理请求时转发给其他实例 |
| **Object System** | 跨实例数据传输系统，支持大对象传递 |

### 架构简图

```
单机部署：1 anyserve 实例 = 1 Agent + N Workers
多机部署：1 anyserve 实例 = M Agents (每机 1 个，leader-follower) + N Workers
```

## 开发命令

```bash
# 构建
just setup    # 安装 C++ 依赖（Conan）
just build    # 编译 C++

# 运行当前版本
anyserve examples.basic.app:app --port 8000 --workers 1

# 测试
python examples/basic/run_example.py
```

## 代码规范

- **C++**：C++17，`namespace anyserve`，Google Style
- **Python**：类型注解，PEP 8，绝对导入
- **Proto**：proto3 语法
- **新文件**：放在 mvp.md 指定的位置

## 验证方式

Phase 1 完成后应能：
```bash
# 启动 API Server
python api_server/main.py --port 8080

# 测试注册接口
curl -X POST http://localhost:8080/register \
  -H "Content-Type: application/json" \
  -d '{"replica_id": "test", "endpoint": "localhost:50051", "capabilities": [{"type": "chat"}]}'

# 查询注册表
curl http://localhost:8080/registry
```

## 注意事项

1. **先读文档再写代码** - architecture.md 和 mvp.md 包含了设计决策
2. **按 Phase 顺序开发** - 不要跳跃，每个 Phase 有依赖关系
3. **使用 @app.capability** - 使用 `@app.capability(type="xxx")` 装饰器定义 handler
4. **MVP 简化** - 不需要实现零拷贝、RDMA 等高级特性，用文件系统模拟 Object System
5. **运行前清除代理** - gRPC 会受 http_proxy 影响导致 localhost 连接失败，运行示例或测试前需清除：
   ```bash
   unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
   ```
