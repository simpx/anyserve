# anyserve Architecture

> **Serve Any models, Any scale, Any where**

anyserve 是一个**面向大规模 LLM 推理的 Serving Runtime**。

---

## 1. 概述

### 核心特征

- **Capability-centric**：以 Capability 为核心抽象，通过动态切换实现资源的灵活复用
- **SLO 驱动**：基于请求队列和 SLO 做调度决策，而非资源利用率
- **Object System**：支持跨实例的高效数据传递

### 架构哲学

**1. 核心抽象：Capability**

Capability 是 anyserve 的一等公民，代表 Worker 能提供的能力。

> **Capability 定义**：从 anyserve 视角看**不可进一步分割**的能力单元。
>
> 判断标准：该能力是否期望接收完整的请求并独立处理。

| 场景 | 底层实现 | Capability 划分 |
|------|----------|-----------------|
| PD 分离 | 2 个 vLLM (prefill + decode) | **2 个** - 各自接收完整请求 |
| 多机 TP | 2 机 NCCL 紧耦合 forward | **1 个** - 协同响应同一请求 |

**2. 核心特征：Capability 动态切换**

同一组资源可以在不同时刻提供不同的 Capability，而非静态绑定某个模型。这使得：
- 资源利用更灵活
- 支持多模型混部
- 适应流量波动

这是 anyserve 区别于静态部署系统的根本特征。

**3. 调度原则：SLO 驱动**

anyserve 基于 **请求队列和 SLO** 而非资源利用率做调度决策。

anyserve 不深入关心：
- Worker 内部的进程数量
- Worker 的 GPU 占用
- Worker 的资源利用率

anyserve 关心：
- 当前有哪些 Capability 可用
- 请求队列的深度和 SLO
- Worker 是否能接收新请求

基于队列状态，anyserve 决定 Worker 的启动、停止、休眠与唤醒。

**4. Worker 视角：声明式配置**

anyserve 对 Worker 采用 **黑盒** 策略，只关心 Worker 的外部行为：
- 声明的 Capability
- 存活状态
- 请求接收能力

Worker 可选择性声明：
- 资源需求（如 GPU 数量）—— 帮助 anyserve 评估启停代价
- 生命周期钩子（on_start, on_cleanup）—— 自定义初始化和清理逻辑

**5. 进程模型：统一管理**

anyserve 作为主进程，负责启动和管理其下属的 Worker 进程。Worker 的生命周期由 anyserve 完全掌控。

### 非目标

anyserve **不是**：
- **全局调度器** —— 这是上层 API Server / Router 的职责
- **资源管理器** —— 这是 K8s / 资源编排层的职责
- **推理引擎** —— 这是 vLLM / sglang 等的职责

---

## 2. 与其他系统对比

| 系统 | 定位 | 与 anyserve 的关系 |
|------|------|-------------------|
| **Ray** | 通用分布式计算框架 | anyserve 专注 LLM Serving，不做通用 task/actor；Object System 采用更简单的 copy 语义 |
| **Triton** | Model Serving Server | Triton 以 model 为中心，静态部署；anyserve 以 Capability 为中心，支持动态切换 |
| **KServe** | K8s 上的 ML Serving | anyserve 复用 KServe 协议；anyserve 是 Runtime 层，KServe 是编排层 |
| **vLLM/sglang** | 推理引擎 | anyserve 管理引擎的生命周期，引擎是 Worker 的内部实现细节 |

---

## 3. 系统分层

```
┌──────────────────────────────────────────────┐
│              API Server / Router              │
│           （独立项目，不属于 anyserve）         │
│   - 请求入口                                  │
│   - 基于 Capability 路由到 anyserve 实例       │
└──────────────────────┬───────────────────────┘
                       │ KServe (控制流)
                       ↓
┌──────────────────────────────────────────────┐
│             anyserve 实例                     │
│              （本项目）                        │
│   - Agent 管理 Worker 生命周期                │
│   - 请求分发、队列、SLO                       │
│   - Object System                            │
└──────────────────────┬───────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────┐
│             资源管理层 (K8s)                  │
│           （不属于 anyserve）                 │
│   - 分配一组资源（单机或多机）                 │
└──────────────────────────────────────────────┘
```

### 职责边界

| 层 | 职责 | 不负责 |
|----|------|--------|
| **API Server** | 全局路由、负载均衡 | 不理解 Worker、不管资源 |
| **anyserve** | Worker 管理、请求分发、Object System | 不做全局路由、不做资源分配 |
| **资源管理层** | 分配/回收资源 | 不理解 Capability |

---

## 4. 核心概念

### anyserve 实例

- 部署单元，运行在一组资源上（单机或多机）
- 对 API Server 暴露 endpoint
- **单机**：1 anyserve 实例 = 1 Agent + N Workers
- **多机**：1 anyserve 实例 = M Agents (leader-follower) + N Workers

### Agent

- anyserve 主进程，每机一个
- 职责：流量入口、Worker 管理、请求队列、Object System
- 多机场景下，Agent 之间通过 leader-follower 模式协调

### Worker

- 执行实际推理的进程
- 1 Worker 提供 1 组 Capability
- 1 Worker 可能使用 1-N 张 GPU
- Agent 不管 Worker 内部细节（TP/EP 等由引擎管理）

### Capability

**任意 key-value 数据**，用于请求路由和匹配。Capability 是 anyserve 的核心抽象，详见 [架构哲学](#架构哲学)。

示例：
```
{type: "chat", model: "llama-70b"}
{type: "embed"}
{model: "llama-70b", tier: "heavy", max_tokens: 8192}
```

### Delegation

- 当 anyserve 实例收到自己无法处理的请求时，转发给其他实例
- 场景：API Server 路由信息滞后，或主动"随便选一个"
- 走 KServe 协议，经过 API Server 重新路由

---

## 5. 部署架构

### 单机部署

```
┌─────────────────────────────────────┐
│         1 machine, 8 GPUs           │
│                                     │
│   ┌─────────────────────────────┐   │
│   │       anyserve 实例          │   │
│   │                             │   │
│   │   Agent                     │   │
│   │      ↓                      │   │
│   │   Workers                   │   │
│   └─────────────────────────────┘   │
│                                     │
└─────────────────────────────────────┘
```

### 多机部署

```
┌─────────────────────────────────────────────────────┐
│              2 machines, 16 GPUs                    │
│                                                     │
│   ┌───────────────────────────────────────────┐    │
│   │            anyserve 实例                   │    │
│   │                                            │    │
│   │   Machine A            Machine B           │    │
│   │   ┌──────────────┐    ┌──────────────┐    │    │
│   │   │ Agent (leader)│    │ Agent (follower)│    │    │
│   │   │      ↓       │    │      ↓       │    │    │
│   │   │ Workers      │    │ Workers      │    │    │
│   │   └──────────────┘    └──────────────┘    │    │
│   │                                            │    │
│   │   Agent 负责在各机器上启动 Worker 进程       │    │
│   │   Worker 内部通信（如 NCCL）由引擎管理       │    │
│   └───────────────────────────────────────────┘    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 6. 进程架构

### 单机场景

```
┌──────────────────────────────────────────────────────────────┐
│                       anyserve 实例                           │
│                                                               │
│   ┌───────────────────────────────────────────────────────┐  │
│   │                      Agent (C++)                       │  │
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
│   │              │   │              │   │              │     │
│   └──────────────┘   └──────────────┘   └──────────────┘     │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

anyserve（Agent）作为主进程，负责启动和管理 Worker 子进程。Worker 的生命周期由 Agent 完全掌控。

### Agent 内部组件

| 组件 | 职责 |
|------|------|
| **Worker Manager** | 管理 Worker 生命周期，动态启停 |
| **Request Queues** | 按 Capability 分队列，SLO 调度 |
| **Object System** | 内存管理，跨实例数据传输 |

---

## 7. Worker 动态管理

**Capability 动态切换**是 anyserve 的核心特性。

### 为什么需要动态启停

- GPU 资源昂贵，不能让所有 Worker 常驻
- 不同时段的 Capability 需求不同
- 支持同一资源上运行不同模型/配置

### SLO 驱动的调度

anyserve 基于 **请求队列和 SLO** 而非资源利用率做调度决策：

| anyserve 关心 | anyserve 不深入关心 |
|--------------|-------------------|
| 当前有哪些 Capability 可用 | Worker 内部的进程数量 |
| 请求队列的深度和 SLO | Worker 的 GPU 占用 |
| Worker 是否能接收新请求 | Worker 的资源利用率 |

基于队列状态，anyserve 决定 Worker 的启动、停止、休眠与唤醒。

### Worker Manager 职责

1. **感知 Worker 状态**：运行中、空闲、可接收请求
2. **启停决策**：根据请求队列深度和 SLO 决定
3. **生命周期管理**：启动、停止、健康检查

### 与静态部署的区别

| | 静态部署（如 Triton） | anyserve |
|---|---|---|
| Worker 数量 | 启动时固定 | 动态变化 |
| Capability | 静态绑定 | 动态切换 |
| 资源利用 | 常驻占用 | 按需启停 |
| 适合场景 | 稳定负载 | 多变负载、多模型混部 |

---

## 8. Request Queues

### 设计目标

- 按 Capability 组织请求队列
- 根据 SLO 要求调度请求
- 配合 Worker Manager 做流量控制

### 核心机制

```
请求进入 Agent
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
  调度决策（基于队列深度、SLO、Worker 状态）
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

Object System 支持跨 anyserve 实例的大对象传递（如图片、Tensor），为多模态推理做准备。

### 核心语义

| 特性 | 说明 |
|------|------|
| **Copy 语义** | 读取得到 copy，无 ownership / 引用计数（简化自 Ray Object） |
| **大数据传输** | 控制流与数据流分离，数据直连传输，不经过 API Server |
| **缓存支持** | 带 key 的 obj 可被缓存，支持跨请求复用 |

### API 示例

```python
# 创建对象
obj = anyserve.create(data)

# 创建带 key（可缓存）
obj = anyserve.create(data, key="user-123-image")

# 跨实例调用
result = anyserve.call(cap={...}, inputs=[obj])

# 查找缓存
obj = anyserve.lookup("user-123-image")
```

> 详细设计见 [object-system.md](object-system.md)

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
   根据 Capability 选择并转发 anyserve 实例
              │
              ↓
3. anyserve Agent 接收
   - 解析 header，提取 Capability
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
1. Agent 收到请求，发现没有匹配的 Worker
              │
              ↓
2. 发起 Delegation
   - 构造新请求（带原始 obj ref）
   - 发送到 API Server
              │
              ↓
3. API Server 重新路由
   - 选择另一个 anyserve 实例
              │
              ↓
4. 目标实例处理并返回
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

    def on_cleanup(self):
        self.engine.shutdown()

    def handle(self, request):
        return self.engine.generate(...)
```

### 声明式配置

Worker 可选择性声明资源需求，帮助 anyserve 评估启停代价：

```python
@app.capability(type="heavy", gpus=8)
def heavy_handler(request):
    ...
```

---

## 附录：术语表

| 术语 | 定义 |
|------|------|
| anyserve 实例 | 部署单元，运行在一组资源上（单机或多机） |
| Agent | anyserve 主进程，每机一个 |
| Worker | 执行推理的进程，提供 Capability |
| Capability | anyserve 的核心抽象，不可分割的能力单元 |
| Delegation | 请求转发机制 |
| Object System | 跨实例数据传输系统 |