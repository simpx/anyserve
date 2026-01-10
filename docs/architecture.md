# anyserve Architecture (SSOT)

> 本文档是 anyserve 的架构单一事实源（Single Source of Truth, SSOT）。
> 
> 目标：
> - 说清 anyserve 的定位、核心抽象、三层边界、关键运行机制
> - 说清 anyserve 的实现层切分（Rust/Python 的职责与进程边界）
> 
> 非目标：
> - 不展开上层调度器与资源管理层的内部算法/实现
> - 不在本文档讨论多机 TP/EP 的具体启动细节（属于后续实现章节）

---

## 1. 定位与目标

anyserve 是一个 **面向大规模 LLM 推理的 Capability-Oriented Serving Runtime**。

它的定位是：在集群环境（如 K8s）之上，为请求级调度器提供一个稳定的执行层，使 LLM 推理能够：

- 以 **capability**（语义能力）为单位进行编排与路由
- 以 **replica**（运行时副本）为单位进行执行与切换
- 满足请求 SLO（延迟、吞吐、稳定性）
- 尽可能少用 GPU（通过编排、binpacking、快速切换等手段）

anyserve **不是**：
- 分布式计算框架（不提供 task/actor 语义）
- 全局请求调度器（不做全局路由策略）
- 资源管理系统（不管理节点/GPU 分配）

---

## 2. 三层架构与职责边界

anyserve 位于三层架构的中间层：

┌──────────────────────────────┐
│ 上层调度器 (Capability Router) │
└──────────────▲───────────────┘
│ request(cap)
│ delegation(cap upgrade)
┌──────────────┴───────────────┐
│ anyserve Runtime │
└──────────────▲───────────────┘
│ start/stop replicas (tier)
│ allocate gang / resources
┌──────────────┴───────────────┐
│ 资源管理层 (K8s / 集群) │
└──────────────────────────────┘


### 2.1 上层调度器（不属于 anyserve）

调度器负责 **请求级路由**，只理解：

- `capability`（请求要的语义能力）
- `replica`（可执行端点）
- `replica load`（负载指标，用于负载均衡/binpacking）

调度器做的事情：

- 维护映射：`capability -> [replica endpoints]`
- 在候选 replicas 中根据 load 做路由：
  - 满足 capability
  - 尽量 binpacking（集中负载以便腾空副本/机器）

调度器 **不需要**理解（也不应理解）：
- GPU 数量/形状
- 单机/多机
- TP/EP/PP 等并行策略
- 引擎细节（vLLM/sglang/自定义逻辑）

> 在调度器眼里：
- replica 不是“万能”的。它只提供自己注册过的 capability 集合。
- 当找不到特定capability可用的replica 时，调度器也会发请求到自认为合适的replica，由replica来委托请求

---

### 2.2 anyserve（属于本项目）

anyserve 是 **request-level serving runtime**，负责：

- 在 replica 内提供 capability
- 请求接入、排队、并发控制、背压、（可选）batch
- 在资源不变前提下进行本地重配置：
  - 切换 capability
  - 拆分/合并本机内的执行形态（in-place reshape）
- 当出现硬不匹配时执行 **delegation（委托）**
- 大对象传输：Object Plane（ObjRef）

anyserve **不负责**：
- 全局路由（那是上层调度器）
- 节点/GPU 的全局分配与扩缩容（那是资源管理层或其生态）

---

### 2.3 资源管理层（不属于 anyserve）

资源管理层负责：

- 管理物理资源（节点、GPU、网络等）
- 根据全局负载决定：
  - 启动/停止 anyserve replicas
  - 为 replica 分配资源规模（可以抽象成少量 tier）
- 在需要多机时，保证 **原子启动（gang）**：
  - 要么一次性分配并启动所需资源组
  - 要么不启动（避免“半拉子资源”暴露给 runtime）

资源层可以维护 **少数离散的资源等级（tier）**，例如：
- standard（常规）
- heavy（重型）

tier 的具体含义（多少 GPU、单机/多机）不要求暴露给调度器与 anyserve runtime；
调度器只通过 capability 语义（如 `decode.heavy`）感知“重型能力”。

---

## 3. 核心抽象

### 3.1 Capability（能力）

Capability 表示一种 **语义计算能力**，而不是模型/接口/资源形态。

示例：

- `prefill`
- `decode`
- `decode.heavy`（重型 decode 能力）
- `embedding`
- `rerank`

Capability 描述的是 “做什么”，不描述 “怎么做”。

---

### 3.2 Replica（运行时载体）

Replica 是 anyserve 的最小运行时单元，用于承载 capability。

一个 replica：

- 运行在一组已分配资源之上（单机或多机）
- 对外暴露一个 endpoint（被调度器路由）
- 注册并提供一组 capability
- 有运行态：ready/busy/draining 等
- 内部实现（TP/EP、多机通信）对调度器透明

> Replica 是不可拆分的执行整体；调度器从不把一个请求拆到多个 replica 上执行。

---

### 3.3 Delegation（委托）

Delegation 是 anyserve 的关键机制，用于解决“入口可承接但本地不可执行”的情况。

当某 replica **无法以当前资源形态**满足某 capability（硬不匹配）时：

- anyserve 将请求 capability **语义升级**（例如：`decode -> decode.heavy`）
- 将升级后的请求重新交由调度器路由到能提供该 capability 的 replica

重要约束：

- delegation 是 **重新路由**，不是 replica 间直接调用
- PoC/MVP 建议限制为 **最多一次委托**，避免转发风暴

---

### 3.4 Object Plane（大对象系统）

anyserve 内置 Object Plane，用于在能力之间/副本之间传递超大中间数据：

- 以 ObjRef 表达（可自动解引用、lazy get）
- 同机尽量 zero-copy（mmap/memoryview）
- 跨机以 copy 为主
- 简化语义：copy-only、TTL 驱动，不做复杂引用计数/lineage

Object Plane 是 anyserve 的一等能力，但不追求成为通用分布式对象存储。

---

## 4. 请求执行模型（request-level serving）

每个请求进入 anyserve replica 后，遵循统一流程：

request(cap)
├─ local can serve cap:
│ execute locally
│
├─ else can reconfigure within allocated resources:
│ reconfigure (switch/split/merge) then execute
│
└─ else (hard mismatch):
cap := upgrade(cap) # e.g. decode -> decode.heavy
delegate to scheduler for re-routing


其中：

- **本地执行** 是默认路径
- **本地重配置** 只在“资源占用不变”的前提下进行（不触发资源层）
- **委托** 用于硬不匹配（例如需要 heavy 能力）

---

## 5. “万能 runtime” 的准确表述

anyserve 不保证每个 replica 都能本地执行所有请求。

anyserve 追求的保证是：

> 任意请求可以发送到任意入口 replica，  
> 入口 replica 会通过本地执行/本地重配置/委托重路由，  
> 为该请求找到一条可执行路径。

也就是说：**万能的是入口语义，不是本地算力。**

---

## 6. 实现架构：Rust + Python

anyserve 采用 **Rust + Python** 的实现分层：

- Rust：高性能 runtime（控制路径）
- Python：执行与生态（执行路径）

### 6.1 Rust Runtime（控制路径）

Rust 负责：

- gRPC/HTTP ingress
- request queue / 并发控制 / 背压（可选 batch）
- capability dispatch（本地路由到 handler）
- delegation（cap upgrade + 调度器重路由）
- Object Plane 的控制面（对象注册、生命周期、传输调度）
- 与 Python Worker 的 IPC（小消息走 IPC，大对象走 ObjRef）

Rust 进程是 replica 的“主进程”，保持长生命周期与高并发能力。

---

### 6.2 Python Worker（执行路径）

Python 负责：

- 用户编写的 capability handler（开发体验类似 FastAPI）
- 推理引擎集成（如 vLLM / sglang）
- torch/tokenizer/自定义业务逻辑

Python Worker 作为 worker 进程运行：

- 接收 Rust runtime 的调用
- 执行 handler，返回结果或 ObjRef
- 不参与全局路由策略与资源决策

---

### 6.3 进程边界（Replica = Rust + Python Workers）

一个 anyserve replica 的典型进程模型：

- 1 个 Rust 主进程（runtime）
- N 个 Python worker 进程（按 capability / runner 类型划分）

跨 replica 的交互（例如委托）通过 **调度器重路由** 完成，而非 replica 直接互调。

---

## 7. 针对 LLM 推理的专项优化（引擎可插拔）

anyserve 支持针对推理引擎的特化 runner（例如 vLLM runner）：

- 引擎生命周期管理（启动/复用/回收）
- 快速模型/配置切换（如 sleep/resume）
- 与 Object Plane 配合复用中间数据（如 KV cache）

这些优化只存在于 anyserve 内部，对调度器与资源层透明。

---

## 8. 设计约束与非目标（Non-Goals）

anyserve 明确不做：

- 全局请求调度（由上层调度器负责）
- 全局资源编排与扩缩容（由资源层负责）
- task/actor 级分布式执行模型（不做 Ray）
- 在 runtime 层理解 TP/EP/PP 的内部细节（这些属于引擎/runner）

---

## 9. 总结

anyserve 的价值在于：

> 在正确的抽象层（Capability/Replica），  
> 用 request-level runtime + delegation 机制，  
> 把复杂的 LLM 推理执行与切换问题变成可路由、可组合、可插拔的运行时问题，  
> 并与上层调度器、下层资源管理清晰解耦。