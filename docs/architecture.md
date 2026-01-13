# anyserve Architecture

> 本文档是 anyserve 的架构设计文档，用于帮助团队理解系统的核心概念、设计原则和实现结构。

---

## 1. 概述

### anyserve 是什么

anyserve 是一个 **面向大规模 LLM 推理的 Serving Runtime**。

它的核心职责是：
- 在一组已分配的资源（Gang）上，管理和调度推理 Worker
- 以 **Capability**（语义能力）为单位进行请求分发
- 支持 **Worker 动态启停**，实现资源的灵活复用
- 提供 **Object System**，实现跨 Replica 的高效数据传递

### 设计原则

1. **Capability 驱动，非 Model 驱动**
   - 调度基于 capability（任意 key-value），不只是 model name
   - 例：`{type: "chat", model: "llama-70b", tier: "heavy"}`

2. **控制流与数据流分离**
   - 控制流：走 KServe 协议，经过 API Server 路由
   - 数据流：Object System 通过 RDMA 直连传输

3. **Replica 抽象屏蔽并行细节**
   - 对外是一个 Replica，内部可能是 DP/TP/EP 任意组合
   - API Server 不需要理解并行策略

4. **Worker 动态启停**
   - Worker Manager 可以根据请求负载动态启停 Worker
   - 这是 anyserve 区别于静态部署系统的核心特性

5. **简化的 Object 语义**
   - Copy 语义，无 ownership 模型
   - Lazy read，按需传输

### 非目标

anyserve **不负责**：
- 全局请求路由（由 API Server 负责）
- 资源分配与扩缩容（由 K8s / 资源管理层负责）
- 推理引擎内部实现（由 vLLM/sglang 等负责）

---

## 2. 与其他系统对比

| 系统 | 定位 | 与 anyserve 的区别 |
|------|------|-------------------|
| **Ray** | 通用分布式计算框架 | anyserve 专注 serving，不做 task/actor；Object System 更简单（copy 语义，无 ownership） |
| **Triton** | Model Serving Server | Triton 以 model 为中心，静态部署；anyserve 以 capability 为中心，动态启停 |
| **KServe** | K8s 上的 ML Serving | anyserve 复用 KServe 协议，但内部架构不同；anyserve 是 Runtime，KServe 是编排层 |
| **vLLM/sglang** | 推理引擎 | anyserve 管理引擎的生命周期，引擎是 Worker 内部的实现 |

---

## 3. 系统分层

```
┌──────────────────────────────────────────────┐
│              API Server                       │
│         （独立项目，不属于 anyserve）           │
│   - 请求入口                                  │
│   - 基于 Capability 路由                      │
└──────────────────────┬───────────────────────┘
                       │ KServe (控制流)
                       ↓
┌──────────────────────────────────────────────┐
│            anyserve Replica                   │
│              （本项目）                        │
│   - 管理 Worker 生命周期                      │
│   - 请求分发、队列、SLO                       │
│   - Object System                            │
└──────────────────────┬───────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────┐
│           资源管理层 (K8s Gang)               │
│         （不属于 anyserve）                   │
│   - 原子分配资源                              │
│   - 单机或多机                                │
└──────────────────────────────────────────────┘
```

### 职责边界

| 层 | 职责 | 不负责 |
|----|------|--------|
| **API Server** | 全局路由、负载均衡 | 不理解 Worker、不管资源 |
| **anyserve** | Worker 管理、请求分发、Object System | 不做全局路由、不做资源分配 |
| **资源管理层** | 分配/回收 Gang | 不理解 Capability |

---

## 4. 核心概念

### Gang

- K8s 分配的一组资源（N 机器 × M GPU）
- 原子分配：要么全给，要么不给
- 例：2 台机器，每台 8 卡 = 1 个 Gang

### Replica

- 运行在一个 Gang 上的 anyserve 实例
- **1 Replica = 1 Gang**
- 对 API Server 暴露 endpoint（入口数量待定）

### Dispatcher

- Replica 的控制中心
- 单机场景下：1 Replica = 1 Dispatcher
- 职责：流量入口、Worker 管理、请求队列、Object System

### Worker

- 执行实际推理的进程
- 1 Worker 提供 1 组 Capability
- 1 Worker 可能使用 1-N 张 GPU
- Dispatcher 不管 Worker 内部细节（TP/EP 等由引擎管理）

### Capability

- **任意 key-value 数据**，用于请求路由和匹配
- 不是固定 schema，由业务定义
- 例：
  ```
  {type: "chat", model: "llama-70b"}
  {type: "embed"}
  {model: "llama-70b", tier: "heavy", max_tokens: 8192}
  ```

### Delegation

- 当 Replica 收到自己无法处理的请求时，转发给其他 Replica
- 场景：API Server 路由信息滞后，或主动"随便选一个"
- 走 KServe 协议，经过 API Server 重新路由

---

## 5. 部署架构

### 单机部署

```
┌─────────────────────────────────────┐
│           Gang (1 machine)          │
│                                     │
│   ┌─────────────────────────────┐   │
│   │      anyserve Replica       │   │
│   │                             │   │
│   │   Dispatcher                │   │
│   │      ↓                      │   │
│   │   Workers (GPU 0-7)         │   │
│   └─────────────────────────────┘   │
│                                     │
└─────────────────────────────────────┘
```

### 多机部署

```
┌─────────────────────────────────────────────────────┐
│              Gang (2 machines, 16 GPUs)             │
│                                                     │
│   ┌───────────────────────────────────────────┐    │
│   │            anyserve Replica                │    │
│   │                                            │    │
│   │   Machine A          Machine B             │    │
│   │   ┌──────────┐      ┌──────────┐          │    │
│   │   │ DP 0     │      │ DP 1     │          │    │
│   │   │ (ep=8)   │      │ (ep=8)   │          │    │
│   │   └──────────┘      └──────────┘          │    │
│   │                                            │    │
│   │   anyserve 负责在两台机器上启动进程         │    │
│   │   EP 内部通信由引擎管理                    │    │
│   └───────────────────────────────────────────┘    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 6. 进程架构

### 单机场景

```
┌──────────────────────────────────────────────────────────────┐
│                     anyserve Replica                          │
│                                                               │
│   ┌───────────────────────────────────────────────────────┐  │
│   │                    Dispatcher (C++)                    │  │
│   │                                                        │  │
│   │   ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │  │
│   │   │   Worker    │  │   Request   │  │    Object    │  │  │
│   │   │   Manager   │  │   Queues    │  │    System    │  │  │
│   │   └─────────────┘  └─────────────┘  └──────────────┘  │  │
│   │                                                        │  │
│   └───────────────────────────┬────────────────────────────┘  │
│                               │ IPC (Unix Socket)             │
│             ┌─────────────────┼─────────────────┐             │
│             ↓                 ↓                 ↓             │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐     │
│   │   Worker 0   │   │   Worker 1   │   │   Worker 2   │     │
│   │   (Python)   │   │   (Python)   │   │   (Python)   │     │
│   │              │   │              │   │              │     │
│   │ cap: chat    │   │ cap: embed   │   │ cap: heavy   │     │
│   │ GPU: 0,1     │   │ GPU: 2       │   │ GPU: 3-7     │     │
│   └──────────────┘   └──────────────┘   └──────────────┘     │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Dispatcher 内部组件

| 组件 | 职责 |
|------|------|
| **Worker Manager** | 管理 Worker 生命周期，动态启停，资源感知 |
| **Request Queues** | 按 Capability 分队列，SLO 调度 |
| **Object System** | 内存管理，跨 Replica 数据传输 |

---

## 7. Worker 动态管理

这是 anyserve 的核心特性之一。

### 为什么需要动态启停

- GPU 资源昂贵，不能让所有 Worker 常驻
- 不同时段的 Capability 需求不同
- 支持同一资源上运行不同模型/配置

### Worker Manager 职责

1. **感知 Worker 状态**：运行中、空闲、资源占用
2. **启停决策**：根据请求队列、SLO、资源情况决定
3. **资源感知**：知道每个 Worker 用了哪些 GPU
4. **生命周期管理**：启动、停止、健康检查

### 与静态部署的区别

| | 静态部署（如 Triton） | anyserve |
|---|---|---|
| Worker 数量 | 启动时固定 | 动态变化 |
| 资源利用 | 常驻占用 | 按需启停 |
| 切换模型 | 重新部署 | 动态切换 |
| 适合场景 | 稳定负载 | 多变负载、多模型 |

---

## 8. Request Queues

### 设计目标

- 按 Capability 组织请求队列
- 根据 SLO 要求调度请求
- 配合 Worker Manager 做流量控制

### 核心机制

```
请求进入 Dispatcher
       │
       ↓
┌─────────────────────────────────────────┐
│            Request Queues               │
│                                         │
│   Queue A          Queue B              │
│   (cap: chat)      (cap: embed)         │
│   ┌─────────┐      ┌─────────┐          │
│   │ req 1   │      │ req 4   │          │
│   │ req 2   │      │ req 5   │          │
│   │ req 3   │      └─────────┘          │
│   └─────────┘                           │
│                                         │
└─────────────────────────────────────────┘
       │
       ↓
  调度决策（基于 SLO、Worker 状态）
       │
       ↓
  分发给 Worker
```

### 调度考量

| 因素 | 说明 |
|------|------|
| **SLO** | 请求的延迟要求，优先级 |
| **队列深度** | 积压情况，是否需要背压 |
| **Worker 状态** | 哪些 Worker 可用，负载如何 |
| **资源情况** | 是否需要启动新 Worker |

### 与 Worker Manager 协作

- 队列积压 → 通知 Worker Manager 启动更多 Worker
- Worker 空闲 → 通知 Worker Manager 可以停止
- 背压 → 拒绝新请求或触发 Delegation

---

## 9. Object System

### 设计目标

- 支持跨 Replica 的大对象传递（如图片、Tensor）
- 尽可能减少内存拷贝
- 为多模态推理（VL、Omni）做准备

### 控制流 vs 数据流分离

```
Replica A                    API Server                   Replica B
    │                            │                            │
    │ ── call(cap, obj_ref) ───► │ ── route ────────────────► │
    │         (KServe)           │        (KServe)            │
    │                            │                            │
    │ ◄─────────────────── RDMA 直连 ───────────────────────► │
    │                    (obj 实际数据)                        │
```

- **控制流**：KServe 协议，经过 API Server 路由
- **数据流**：RDMA 直连，不经过 API Server

### 核心特性

| 特性 | 说明 |
|------|------|
| **Lazy Read** | obj ref 传递时不传数据，读取时才拉取 |
| **Copy 语义** | 读取得到 copy，无 ownership / 引用计数 |
| **与 Dispatcher 集成** | 请求数据直接写入 Object System 内存 |
| **Cache** | 可选，带 key 的 obj 可被缓存，由 Tracker 管理 |

### API 示例

```python
# 直接从 URL 创建
obj = anyserve.fetch("http://example.com/image.jpg")

# 创建带 key（可缓存）
obj = anyserve.create(data, key="user-123-image")

# 跨 Replica 调用
result = anyserve.call(cap={...}, inputs=[obj])

# 查找缓存
obj = anyserve.lookup("user-123-image")
```

---

## 10. 请求流程

### 完整路径

```
1. Client 发送请求
   headers: {x-cap-type: "chat", x-cap-model: "llama-70b"}
   body: <input data>
              │
              ↓
2. API Server 路由
   根据 capability 选择 Replica
              │
              ↓
3. anyserve Dispatcher 接收
   - 解析 header，提取 capability
   - body 数据写入 Object System
   - 查找匹配的 Worker
              │
              ↓
4. 分发给 Worker
   - 传递 obj ref
   - Worker 执行推理
              │
              ↓
5. 返回响应
```

### Delegation 流程

```
1. Dispatcher 收到请求，发现没有匹配的 Worker
              │
              ↓
2. 发起 Delegation
   - 构造新请求（带原始 obj ref）
   - 发送到 API Server
              │
              ↓
3. API Server 重新路由
   - 选择另一个 Replica
              │
              ↓
4. 目标 Replica 处理并返回
```

---

## 11. Worker 定义

### 装饰器方式（简单场景）

```python
from anyserve import AnyServe

app = AnyServe()

@app.capability(type="chat", model="llama-70b")
def chat_handler(request):
    return response

@app.capability(type="embed")
def embed_handler(request):
    return response
```

### 类方式（需要生命周期管理）

```python
from anyserve import AnyServe, Worker

app = AnyServe()

@app.worker(
    capabilities=[
        {"type": "chat", "model": "llama-70b"},
        {"type": "chat", "model": "llama-7b"},
    ],
    gpus=2
)
class ChatWorker(Worker):
    def on_start(self):
        self.engine = vllm.LLM(...)

    def on_stop(self):
        self.engine.shutdown()

    def handle(self, request):
        return self.engine.generate(...)
```

### 资源声明

Worker 需要声明资源占用，供 Worker Manager 决策：

```python
@app.capability(type="heavy", gpus=8)
def heavy_handler(request):
    ...
```

---

## 附录：术语表

| 术语 | 定义 |
|------|------|
| Gang | K8s 分配的一组资源 |
| Replica | 运行在 Gang 上的 anyserve 实例 |
| Dispatcher | Replica 的控制进程 |
| Worker | 执行推理的进程 |
| Capability | 任意 key-value，用于请求匹配和路由 |
| Delegation | 请求转发机制 |
| Object System | 跨 Replica 数据传输系统 |
