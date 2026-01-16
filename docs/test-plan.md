# AnyServe MVP 测试计划

## 1. 测试概述

本文档定义 AnyServe MVP 的测试策略和测试用例。

### 测试目标

1. **验证核心功能**：确保 MVP 各组件按设计工作
2. **确保代码质量**：通过单元测试覆盖关键逻辑
3. **回归防护**：防止后续修改破坏现有功能

### 测试分层

| 层级 | 描述 | 工具 |
|------|------|------|
| 单元测试 | 测试独立组件 | pytest |
| 集成测试 | 测试组件间交互 | pytest + httpx |
| 端到端测试 | 测试完整流程 | shell script |

---

## 2. 单元测试计划

### 2.1 Object System (`tests/unit/objects/`)

#### test_object_store.py

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_create_object_pickle` | 创建 pickle 格式对象 | P0 |
| `test_create_object_json` | 创建 JSON 格式对象 | P0 |
| `test_create_object_bytes` | 创建 bytes 格式对象 | P0 |
| `test_get_object_by_ref` | 通过 ObjRef 读取对象 | P0 |
| `test_get_object_by_path` | 通过路径字符串读取对象 | P1 |
| `test_delete_object` | 删除对象 | P1 |
| `test_object_exists` | 检查对象是否存在 | P1 |
| `test_list_objects` | 列出所有对象 | P2 |
| `test_cleanup_old_objects` | 清理过期对象 | P2 |
| `test_custom_key` | 使用自定义 key 创建对象 | P1 |

#### test_obj_ref.py

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_obj_ref_to_dict` | ObjRef 序列化为 dict | P0 |
| `test_obj_ref_from_dict` | 从 dict 反序列化 ObjRef | P0 |
| `test_obj_ref_to_string` | ObjRef 序列化为字符串 | P0 |
| `test_obj_ref_from_string` | 从字符串反序列化 ObjRef | P0 |

---

### 2.2 Capability Registry (`tests/unit/api_server/`)

#### test_registry.py

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_register_replica` | 注册新 Replica | P0 |
| `test_register_duplicate_replica` | 重复注册更新 capabilities | P0 |
| `test_unregister_replica` | 注销 Replica | P0 |
| `test_unregister_nonexistent` | 注销不存在的 Replica | P1 |
| `test_lookup_exact_match` | 精确匹配 capability | P0 |
| `test_lookup_partial_match` | 部分匹配 (只有 type) | P0 |
| `test_lookup_no_match` | 无匹配返回 None | P0 |
| `test_lookup_exclude_replica` | 排除指定 Replica 查找 | P0 |
| `test_list_all_replicas` | 列出所有 Replica | P1 |
| `test_get_all_capabilities` | 获取所有 capabilities | P1 |
| `test_health_check` | 健康检查功能 | P2 |

---

### 2.3 Capability Decorator (`tests/unit/kserve/`)

#### test_capability.py

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_capability_init` | Capability 初始化 | P0 |
| `test_capability_matches_exact` | 精确匹配查询 | P0 |
| `test_capability_matches_partial` | 部分匹配查询 | P0 |
| `test_capability_no_match` | 不匹配的查询 | P0 |
| `test_capability_to_dict` | 转换为 dict | P1 |

#### test_context.py

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_context_objects_access` | 访问 ObjectStore | P0 |
| `test_context_objects_not_configured` | ObjectStore 未配置时报错 | P1 |
| `test_context_call_not_configured` | call 未配置时报错 | P1 |

#### test_anyserve_app.py

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_capability_decorator` | @app.capability 装饰器 | P0 |
| `test_capability_decorator_uses_context` | 检测 context 参数 | P0 |
| `test_get_capabilities` | 获取注册的 capabilities | P0 |
| `test_find_handler_exact` | 精确查找 handler | P0 |
| `test_find_handler_partial` | 部分匹配查找 | P0 |
| `test_find_handler_no_match` | 无匹配返回 None | P0 |

#### test_stream.py (Phase 7)

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_stream_init` | Stream 初始化 | P0 |
| `test_stream_send` | 发送消息到 stream | P0 |
| `test_stream_send_multiple` | 发送多个消息 | P0 |
| `test_stream_close` | 关闭 stream | P0 |
| `test_stream_send_after_close_raises` | 关闭后发送抛出异常 | P0 |
| `test_stream_error` | 发送错误响应 | P0 |
| `test_stream_iter_responses` | iter_responses 生成器 | P0 |
| `test_stream_iterator_protocol` | 迭代器协议 | P1 |
| `test_stream_threaded_producer_consumer` | 多线程生产者-消费者模式 | P0 |

---

### 2.4 API Server Router (`tests/unit/api_server/`)

#### test_router.py

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_health_endpoint` | GET /health | P0 |
| `test_register_endpoint` | POST /register | P0 |
| `test_unregister_endpoint` | DELETE /unregister | P0 |
| `test_registry_endpoint` | GET /registry | P0 |
| `test_infer_json_endpoint` | POST /infer/json | P0 |
| `test_infer_routing_by_type` | 按 type 路由 | P0 |
| `test_infer_routing_by_model` | 按 type+model 路由 | P0 |
| `test_infer_no_replica` | 无匹配 Replica | P1 |
| `test_delegation_header` | 处理 delegation header | P1 |

---

## 3. 集成测试计划 (`tests/integration/`)

### test_api_server_integration.py

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_full_register_lookup_flow` | 注册 → 查询 → 路由 | P0 |
| `test_multiple_replicas` | 多 Replica 场景 | P0 |
| `test_delegation_flow` | Delegation 流程 | P1 |

### test_object_passing.py

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_create_and_read_object` | 创建并读取对象 | P0 |
| `test_object_ref_serialization` | ObjRef 序列化传递 | P0 |

### test_streaming.py (Phase 7)

| 测试用例 | 描述 | 优先级 |
|---------|------|--------|
| `test_register_streaming_handler` | 注册流式 handler | P0 |
| `test_find_stream_handler` | 查找流式 handler | P0 |
| `test_find_stream_handler_not_found` | 流式 handler 未找到 | P0 |
| `test_find_handler_excludes_stream` | 非流式查找排除流式 handler | P0 |
| `test_find_any_handler_finds_stream` | find_any_handler 查找流式 | P0 |
| `test_both_streaming_and_non_streaming` | 同时支持流式和非流式 | P0 |
| `test_streaming_handler_full_flow` | 完整流式执行流程 | P0 |
| `test_streaming_handler_with_delay` | 带延迟的流式 handler | P1 |
| `test_streaming_handler_error` | 流式 handler 错误处理 | P0 |
| `test_stream_handler_with_multiple_attrs` | 多属性流式 handler | P1 |

---

## 4. 端到端测试 (`examples/mvp_demo/`)

### test_client.py (已实现)

| 测试用例 | 描述 |
|---------|------|
| `test_registry` | 验证注册表 |
| `test_chat_capability` | 测试 chat 路由 |
| `test_embed_capability` | 测试 embed 路由 |
| `test_heavy_capability` | 测试 heavy 路由 |
| `test_object_passing` | 测试对象传递 |

### test_stream_client.py (Phase 7)

| 测试用例 | 描述 |
|---------|------|
| `test_streaming` | 测试流式推理端点 |
| `test_non_streaming` | 测试非流式端点对比 |

---

## 5. 运行测试

### 安装测试依赖

```bash
pip install pytest pytest-asyncio pytest-cov httpx
```

### 运行所有测试

```bash
# 运行所有单元测试
pytest tests/unit -v

# 运行特定组件测试
pytest tests/unit/objects -v
pytest tests/unit/api_server -v
pytest tests/unit/kserve -v

# 运行集成测试
pytest tests/integration -v

# 生成覆盖率报告
pytest tests/unit --cov=python/anyserve --cov-report=html
```

### 测试标记

```bash
# 只运行快速测试
pytest -m "not slow"

# 只运行 P0 优先级测试
pytest -m "p0"
```

---

## 6. 覆盖率目标

| 组件 | 目标覆盖率 |
|------|-----------|
| `objects/store.py` | ≥ 90% |
| `api_server/registry.py` | ≥ 90% |
| `api_server/router.py` | ≥ 80% |
| `kserve.py` (Capability 相关) | ≥ 85% |

---

## 7. CI 集成

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Run tests
        run: |
          pytest tests/unit -v --cov=python/anyserve
```
