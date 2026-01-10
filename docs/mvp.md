# anyserve PoC / MVP Scope

本文档明确 anyserve PoC 的 **目标、边界与非目标**，
用于防止实现过程中跑偏或过度设计。

---

## 1. MVP 目标（必须实现）

### 1.1 Capability 路由闭环

- Replica 启动时向调度器注册：
  - replica_id
  - endpoint
  - capability 列表
- 调度器维护：
  - `capability → replicas` 映射
- 请求根据 capability 被正确路由

---

### 1.2 anyserve Runtime 基本能力

- Rust runtime 接收请求（HTTP 即可）
- 解析请求中的 capability
- 判断是否本地可执行

---

### 1.3 Delegation 机制（核心）

- 当本地 replica 无法执行 capability（硬不匹配）时：
  - capability 升级（如 `decode → decode.heavy`)
  - 调用调度器重新路由
  - 将请求转发到新 replica
- PoC 中 **最多允许 1 次 delegation**

---

### 1.4 Rust + Python 执行模型

- Rust 作为主 runtime 进程
- Python worker 作为执行进程
- Rust 通过 IPC 调用 Python handler
- Python handler 返回执行结果

---

### 1.5 Demo 场景（必须跑通）

- Replica S1：
  - capabilities: `decode`
- Replica H1：
  - capabilities: `decode.heavy`

场景：

1. 请求 `decode` → S1 本地执行
2. 请求 `decode.heavy` → S1 触发 delegation → H1 执行

---

## 2. 明确不做的事情（Non-Goals）

以下内容 **刻意不进入 PoC**：

- 多机 TP / EP
- 真正的 K8s operator / autoscaler
- 真正的 gang scheduling
- 完整的 object store（仅 stub）
- 复杂 batching / 优先级调度
- Streaming / 长连接

---

## 3. 实现约束（Implementation Constraints）

- capability 必须是字符串（header 或字段）
- runtime 不直接调用其他 replica
- 跨 replica 一律通过调度器重路由
- 不允许递归 delegation（防止转发风暴）

---

## 4. 成功标准（Exit Criteria）

PoC 视为成功，当且仅当：

- capability 路由与 delegation 行为符合预期
- 任意请求发送到任意入口 replica 都能得到正确执行
- 代码结构清晰，职责边界明确
- 可以自然扩展到 multi-tier / multi-replica 场景

---

## 5. 下一步（PoC 之后）

PoC 完成后，才考虑：

- 多 capability pipeline
- 更复杂的本地重配置
- 对 vLLM 的深度集成
- Object Plane 的真实实现
