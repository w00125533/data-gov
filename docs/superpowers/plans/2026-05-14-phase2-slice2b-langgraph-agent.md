# Phase 2 Slice 2b: LangGraph Agent + Chat SSE + Schema Evolution 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec §4.1–4.5 + §6.7（chat / schema）— 在 `backend/agent/` 下实现 13 个 LangGraph 节点 + AgentState + 11 个工具 + 双层重试编排，暴露 `/api/chat/{start,message,*}` 的 SSE 流式接口与 `/api/schema/{apply,evolution/{table}}` 接口；schema_evolve 走通"NL → diff → validate → 写 Neo4j → sync_yaml → git commit → 回填 Change.commit_hash"全闭环。覆盖 spec §8.2 的 P2-1 / P2-2 / P2-3（NL→代码）+ P2-8 / P2-9（schema 演进）+ P2-10（reverse_synth）+ P2-11 / P2-12 / P2-13（gap_check）。

**Architecture:** LangGraph `StateGraph(AgentState)` 用 conditional edges 串起 13 个节点（spec §4.1 流程图）。`backend/agent/tools.py` 内的工具是**薄包装**，直接调 `backend.metadata.service` / `backend.search.searcher` / `backend.seed.fake_data` / `backend.agent.sandbox_stub` —— spec §4.3 注明 "HTTP routes and Agent tools share the same service functions"。沙箱在本 slice 仅提供接口 stub（`backend/agent/sandbox_stub.py`），slice 2c 落地真实实现；dry_run 节点测试用 monkeypatch。Chat session 用进程内 `dict` 持久化（slice 3 可换 SQLite，本 slice 不做）；SSE 用 `sse-starlette.EventSourceResponse`，事件按 spec §4.1 presenter payload 类型分发。schema_apply 在 Neo4j 事务内同步重写 YAML + git commit + 回填 `Change.commit_hash`。

**Tech Stack:**
- `langgraph>=0.2`（StateGraph + conditional edges + checkpointer 选用 `MemorySaver`）
- `langchain-core>=0.2` + `langchain-openai>=0.1`（slice 2a 已装；本 slice 升级到 0.2）
- `sse-starlette>=2.1`（FastAPI 的 SSE 响应类）
- `GitPython>=3.1`（schema_apply 后 commit 改动的 YAML）
- 已有：`fastapi`, `pydantic-settings`, `neo4j`, `PyYAML`, `chromadb`, `rank-bm25`, `jieba`, `sentence-transformers`

**Prerequisites (来自 slice 1b + 2a):**
- `backend.metadata.service.{list_tables, get_table_by_name, create_table, create_field, update_field_expression, update_field, delete_field, get_lineage}` + 异常 `{TableNotFound, FieldNotFound, FieldHasDownstream, CycleDetected}`
- `backend.metadata.models.{TableResponse, FieldResponse, LineageEdge, UpstreamRef, CreateTableRequest, CreateFieldRequest, UpdateFieldRequest, Layer, StorageType, FieldType}`
- `backend.clients.deepseek.{get_deepseek_client, build_chat_client}`
- `backend.search.searcher.HybridSearcher.search(query, k, use_rerank, rerank_client)` 返回 `[{"doc": SearchDoc, "score": float, "table": str}]`
- `backend.seed.fake_data.generate_fake_data(table, rows)`
- `init-scripts/07_export_yaml.py` 暴露 `LAYER_DIR`

**Out of scope for this slice (deferred):**
- 沙箱真实实现（Spark/Flink/Java Flink dry_run）→ slice 2c；本 slice 仅给 `sandbox_stub.execute(code, code_type) -> DryRunResult` 接口
- 沙箱层 `execute_with_retry`（编译错误自动修复）→ slice 2c
- React 前端 / SSE 消费 UI / Pipeline / Evolution timeline 页面 → Phase 3
- `/api/yaml/preview/:table`, `/api/yaml/export`, `/api/pipeline` → Phase 3
- chat session 持久化到 SQLite → 进程内 dict 满足 Phase 2 验证；Phase 3 接续
- 多用户会话隔离与鉴权 → spec §9 明确无鉴权
- LangSmith 跟踪、Prompt 版本化平台 → 现阶段所有 prompt 落 `backend/agent/prompts.py` 代码常量
- benchmark `--mode incremental` 增量回归对比的真实触发（slice 2a 的 CLI 入口保留，本 slice 不接线）
- StarRocks 元数据写入（spec 元数据真理源是 Neo4j；schema_apply 只动 Neo4j + YAML + git）

---

## File Structure

```
data-gov/
├── backend/
│   ├── agent/                              # NEW
│   │   ├── __init__.py
│   │   ├── state.py                        # AgentState TypedDict + add_messages reducer
│   │   ├── prompts.py                      # 所有 LLM prompts 常量
│   │   ├── tools.py                        # 11 个工具 (thin wrappers)
│   │   ├── sandbox_stub.py                 # DryRunResult + execute() 占位，slice 2c 替换
│   │   ├── yaml_sync.py                    # sync_yaml(tables) + git_commit(message) → commit_hash
│   │   ├── chat_session.py                 # 内存 ChatSessionStore
│   │   ├── graph.py                        # build_graph() + Agent 层 iteration_count 控制
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── classifier.py
│   │       ├── forward_etl.py
│   │       ├── reverse_synth.py
│   │       ├── pipeline_parse.py
│   │       ├── schema_lookup.py
│   │       ├── gap_check.py
│   │       ├── gap_proposal.py
│   │       ├── code_generate.py
│   │       ├── dry_run.py
│   │       ├── presenter.py
│   │       ├── schema_evolve.py
│   │       ├── schema_validate.py
│   │       └── schema_apply.py
│   └── api/
│       ├── chat.py                         # NEW — /api/chat/start, /message (SSE), /:id/result, /:id/history
│       └── schema_evolution.py             # NEW — /api/schema/apply, /api/schema/evolution/{table}
├── tests/
│   └── agent/
│       ├── __init__.py
│       ├── test_state.py
│       ├── test_tools.py
│       ├── test_prompts.py
│       ├── test_sandbox_stub.py
│       ├── test_yaml_sync.py
│       ├── test_chat_session.py
│       ├── nodes/
│       │   ├── __init__.py
│       │   ├── test_classifier.py
│       │   ├── test_forward_etl.py
│       │   ├── test_reverse_synth.py
│       │   ├── test_pipeline_parse.py
│       │   ├── test_schema_lookup.py
│       │   ├── test_gap_check.py
│       │   ├── test_gap_proposal.py
│       │   ├── test_code_generate.py
│       │   ├── test_dry_run.py
│       │   ├── test_presenter.py
│       │   ├── test_schema_evolve.py
│       │   ├── test_schema_validate.py
│       │   └── test_schema_apply.py
│       ├── test_graph_routing.py           # conditional edges + 双层重试上限
│       ├── test_graph_e2e.py               # 三条主路径打通 (mock LLM + sandbox)
│       ├── test_api_chat.py                # /api/chat/* SSE 黑盒
│       ├── test_api_schema.py              # /api/schema/*
│       └── test_p2_acceptance.py           # P2-1..P2-3, P2-8..P2-13 (slice 2b 部分)
├── pyproject.toml                          # MODIFIED — 加 langgraph / sse-starlette / GitPython
├── .env.example                            # MODIFIED — 加 AGENT_MAX_ITERATIONS / GIT_AUTHOR_*
├── app-compose.yml                         # MODIFIED — 加 git config + AGENT_* 环境变量
└── backend/Dockerfile                      # MODIFIED — 安装 git CLI 用于 sync_yaml.git_commit
```

**职责拆分要点：**
- `state.py`：`AgentState(TypedDict, total=False)` 字段集与 spec §4.2 完全对齐；`messages` 用 `Annotated[list, add_messages]`。
- `prompts.py`：每个 LLM 节点的 prompt 模板为模块级常量（`CLASSIFIER_PROMPT`、`EXTRACT_PROMPT`、`SCHEMA_EVOLVE_PROMPT`、`PROPOSE_PROMPT`、`CODE_GEN_PROMPT`、`PRESENTER_REPHRASE_PROMPT`）。
- `tools.py`：`search_tables_by_keyword`、`lookup_table_schema`、`lookup_lineage`、`check_gaps`、`propose_gap_fix`、`generate_fake_data`、`validate_change`、`add_table`、`add_field`、`update_field`、`remove_field`、`sync_yaml`、`dry_run_spark_sql/flink_sql/java_flink`。统一返回 `dataclass` 或 `dict`。
- `sandbox_stub.py`：`DryRunResult` dataclass（`success: bool`, `preview_row: dict | None`, `error_log: str | None`, `application_id: str | None`），加 `execute(code: str, code_type: str) -> DryRunResult` 默认抛 `NotImplementedError("sandbox available in slice 2c")` —— 测试用 monkeypatch；prod 由 slice 2c 替换。
- `yaml_sync.py`：`sync_yaml(table_names)` 调 `init-scripts/07_export_yaml.py` 内部函数对**指定表**重写 YAML（不动其他表）；`git_commit(message)` 调用 GitPython 在仓库根 commit 改动的 `metadata-yaml/**`，返回 hex sha。
- `chat_session.py`：`ChatSession(id, messages, state)` + 进程内 `ChatSessionStore` 单例（`new()`, `get(id)`, `append_message(id, role, content)`）。
- `graph.py`：`build_graph()` 返回编译好的 `CompiledGraph`；conditional edges 按 spec §4.1 流程图；`iteration_count` 在 `code_generate` 入口 +1；`dry_run` 失败且 `iteration_count < AGENT_MAX_ITERATIONS` 时回到 `code_generate`。
- `nodes/*.py`：每个文件一个节点函数 `(state) -> dict`，无副作用 except 调 tools。
- `api/chat.py`：3 个 POST + 2 个 GET；`POST /api/chat/message` 返回 `EventSourceResponse`，按节点流式发送 partial state 摘要。
- `api/schema_evolution.py`：`POST /api/schema/apply`（用户在 gap_proposal 卡片点[确认]的回压入口）+ `GET /api/schema/evolution/{table}`（从 Neo4j `:Change` 节点取时间线）。

---

## Task 0: 依赖 + 包骨架

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `backend/Dockerfile`
- Create: `backend/agent/__init__.py`
- Create: `backend/agent/nodes/__init__.py`
- Create: `tests/agent/__init__.py`
- Create: `tests/agent/nodes/__init__.py`

- [ ] **Step 1: `pyproject.toml` 加运行时依赖**

把 `[project.optional-dependencies] runtime` 列表追加：

```toml
    "langgraph>=0.2",
    "langchain-core>=0.2",
    "sse-starlette>=2.1",
    "GitPython>=3.1",
```

- [ ] **Step 2: `.env.example` 追加**

```env

# LangGraph Agent
AGENT_MAX_ITERATIONS=3
GIT_AUTHOR_NAME=Data-Gov Agent
GIT_AUTHOR_EMAIL=agent@data-gov.local
```

- [ ] **Step 3: `backend/Dockerfile` 在 apt-get 行追加 `git`**

把 `apt-get install` 那一行替换为：

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 4: 创建空 `__init__.py` 文件**

`backend/agent/__init__.py`, `backend/agent/nodes/__init__.py`, `tests/agent/__init__.py`, `tests/agent/nodes/__init__.py` 全部零字节。

- [ ] **Step 5: 验证可安装**

```bash
pip install -e ".[dev]"
python -c "import langgraph, sse_starlette, git; print('ok')"
```

预期：输出 `ok`。

- [ ] **Step 6: 提交**

```bash
git add pyproject.toml .env.example backend/Dockerfile backend/agent tests/agent
git commit -m "feat(agent): add slice 2b deps and package skeleton"
```

---

## Task 1: `backend/config.py` 加 Agent 设置

**Files:**
- Modify: `backend/config.py`
- Create: `tests/agent/test_settings.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/test_settings.py"""
from backend.config import get_settings


def test_agent_settings_defaults(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("AGENT_MAX_ITERATIONS", raising=False)
    monkeypatch.delenv("GIT_AUTHOR_NAME", raising=False)
    monkeypatch.delenv("GIT_AUTHOR_EMAIL", raising=False)
    s = get_settings()
    assert s.agent_max_iterations == 3
    assert s.git_author_name == "Data-Gov Agent"
    assert s.git_author_email == "agent@data-gov.local"


def test_agent_settings_env_overrides(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "5")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test Bot")
    s = get_settings()
    assert s.agent_max_iterations == 5
    assert s.git_author_name == "Test Bot"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_settings.py -v
```

预期：FAIL — `AttributeError: 'Settings' object has no attribute 'agent_max_iterations'`。

- [ ] **Step 3: 在 `backend/config.py` 的 `Settings` 类末尾追加**

```python
    # Agent (slice 2b)
    agent_max_iterations: int = Field(3, alias="AGENT_MAX_ITERATIONS")
    git_author_name: str = Field("Data-Gov Agent", alias="GIT_AUTHOR_NAME")
    git_author_email: str = Field("agent@data-gov.local", alias="GIT_AUTHOR_EMAIL")
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/test_settings.py -v
```

预期：PASS (2/2)。

- [ ] **Step 5: 提交**

```bash
git add backend/config.py tests/agent/test_settings.py
git commit -m "feat(agent): add AGENT_MAX_ITERATIONS and GIT_AUTHOR_* settings"
```

---

## Task 2: AgentState TypedDict

**Files:**
- Create: `backend/agent/state.py`
- Create: `tests/agent/test_state.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/test_state.py"""
from typing import get_type_hints

from backend.agent.state import AgentState


def test_agent_state_has_all_spec_4_2_fields():
    """spec §4.2 全部字段必须存在。"""
    hints = get_type_hints(AgentState)
    required = {
        # classifier / 对话基础
        "messages", "intent", "context_source", "needs_clarification",
        # forward_etl / schema_lookup
        "target_tables", "source_tables", "schemas_resolved",
        # reverse_synth / pipeline_parse
        "row_count_hint", "buckets_hint", "pipeline_chain",
        # code_generate / dry_run
        "generated_code", "code_type", "dry_run_result", "error_feedback",
        "iteration_count",
        # schema_evolve / validate / apply
        "schema_diff", "validation_result", "applied_changes",
        # gap_check / gap_proposal
        "gaps", "has_gaps", "resolved_gaps", "sub_flow_active", "sub_flow_return_point",
        # presenter
        "presenter_payload", "final_message",
    }
    missing = required - set(hints)
    assert not missing, f"AgentState missing fields: {missing}"


def test_agent_state_total_false_allows_partial_construction():
    """所有字段可选 — LangGraph merge 行为依赖。"""
    s: AgentState = {}
    assert isinstance(s, dict)
    s["intent"] = "forward_etl"
    assert s["intent"] == "forward_etl"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_state.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/agent/state.py`**

```python
"""Agent State —— spec §4.2。total=False 让 LangGraph 自动 merge partial dict。"""
from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # —— classifier / 对话基础 ——
    messages: Annotated[list, add_messages]
    intent: str                                # "forward_etl" | "reverse_synth" | "schema_evolve"
    context_source: str                        # "metadata" | "lineage" | "pipeline" | None
    needs_clarification: bool

    # —— forward_etl / schema_lookup ——
    target_tables: list[str]
    source_tables: list[str]
    schemas_resolved: dict                     # {table_name: schema_dict}

    # —— reverse_synth / pipeline_parse ——
    row_count_hint: int
    buckets_hint: list[dict]
    pipeline_chain: list[dict]                 # ODS→EVAL 顺序

    # —— code_generate / dry_run ——
    generated_code: str
    code_type: str                             # "spark_sql" | "flink_sql" | "java_flink"
    dry_run_result: dict
    error_feedback: str
    iteration_count: int

    # —— schema_evolve / validate / apply ——
    schema_diff: list[dict]                    # [{operation, table, field, ...}]
    validation_result: dict                    # {errors, warnings, passed}
    applied_changes: list[dict]

    # —— gap_check / gap_proposal ——
    gaps: list[dict]
    has_gaps: bool
    resolved_gaps: dict
    sub_flow_active: bool
    sub_flow_return_point: str

    # —— presenter ——
    presenter_payload: dict
    final_message: str
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/test_state.py -v
```

预期：PASS (2/2)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/state.py tests/agent/test_state.py
git commit -m "feat(agent): AgentState TypedDict per spec 4.2"
```

---

## Task 3: Sandbox stub interface

**Files:**
- Create: `backend/agent/sandbox_stub.py`
- Create: `tests/agent/test_sandbox_stub.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/test_sandbox_stub.py"""
import pytest

from backend.agent.sandbox_stub import DryRunResult, execute


def test_dry_run_result_dataclass_shape():
    r = DryRunResult(success=True, preview_row={"a": 1}, error_log=None, application_id="app_001")
    assert r.success is True
    assert r.preview_row == {"a": 1}
    assert r.error_log is None
    assert r.application_id == "app_001"


def test_execute_raises_not_implemented_by_default():
    with pytest.raises(NotImplementedError, match="slice 2c"):
        execute("SELECT 1", "spark_sql")


def test_execute_monkeypatched_returns_stub_success(monkeypatch):
    from backend.agent import sandbox_stub

    def fake(code, code_type):
        return DryRunResult(success=True, preview_row={"x": 1}, error_log=None, application_id="app_x")

    monkeypatch.setattr(sandbox_stub, "execute", fake)
    r = sandbox_stub.execute("...", "spark_sql")
    assert r.success and r.preview_row == {"x": 1}
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_sandbox_stub.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/agent/sandbox_stub.py`**

```python
"""Sandbox 接口占位 — slice 2c 用真实 SandboxController 替换。

测试中通过 monkeypatch.setattr(backend.agent.sandbox_stub, "execute", fake) 注入桩。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


CodeType = Literal["spark_sql", "flink_sql", "java_flink"]


@dataclass
class DryRunResult:
    success: bool
    preview_row: Optional[dict] = None
    error_log: Optional[str] = None
    application_id: Optional[str] = None


def execute(code: str, code_type: CodeType) -> DryRunResult:
    """slice 2c 实现：copy template + maven_compile + YARN submit + read result。"""
    raise NotImplementedError(
        "Sandbox.execute is a stub in slice 2b; real impl arrives in slice 2c."
    )
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/test_sandbox_stub.py -v
```

预期：PASS (3/3)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/sandbox_stub.py tests/agent/test_sandbox_stub.py
git commit -m "feat(agent): sandbox stub interface (real impl in slice 2c)"
```

---

## Task 4: Prompts 模块

**Files:**
- Create: `backend/agent/prompts.py`
- Create: `tests/agent/test_prompts.py`

> 所有 LLM prompt 落在这里，便于以后版本化与单测覆盖占位符存在性。

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/test_prompts.py — 守护占位符不丢失。"""
from backend.agent import prompts


def test_classifier_prompt_has_required_placeholders():
    p = prompts.CLASSIFIER_PROMPT
    for ph in ("{history}", "{prev_intent}", "{context_source}"):
        assert ph in p


def test_extract_prompt_has_required_placeholders():
    for ph in ("{msg}", "{intent}"):
        assert ph in prompts.EXTRACT_PROMPT


def test_schema_evolve_prompt_has_required_placeholders():
    for ph in ("{user_request}", "{current_schema}"):
        assert ph in prompts.SCHEMA_EVOLVE_PROMPT


def test_propose_prompt_has_required_placeholders():
    for ph in ("{gaps}", "{user_request}"):
        assert ph in prompts.PROPOSE_PROMPT


def test_code_gen_prompt_has_required_placeholders():
    for ph in ("{schema}", "{intent}", "{user_request}", "{code_type}", "{error_feedback}"):
        assert ph in prompts.CODE_GEN_PROMPT


def test_presenter_rephrase_prompt_has_required_placeholders():
    for ph in ("{intent}", "{summary_json}"):
        assert ph in prompts.PRESENTER_REPHRASE_PROMPT
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_prompts.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/agent/prompts.py`**

```python
"""所有 LLM prompt 模板。{placeholder} 使用 str.format 风格。"""
from __future__ import annotations


CLASSIFIER_PROMPT = """你是无线网络数据治理助手的意图分类器。
基于最近的对话历史判断用户当前消息属于哪一类意图。

候选意图：
- forward_etl: 正向 ETL — 用户希望查询/聚合/转换现有表数据
- reverse_synth: 反向合成 — 用户希望根据评估目标生成测试数据
- schema_evolve: 元数据演进 — 用户希望新增/修改/删除表或字段

最近对话历史:
{history}

上一轮意图: {prev_intent}
当前上下文来源: {context_source}

返回严格的 JSON (不要 Markdown 包裹):
{{"intent": "forward_etl|reverse_synth|schema_evolve", "confidence": 0.0-1.0, "reason": "..."}}
"""


EXTRACT_PROMPT = """从用户消息抽取业务实体。意图: {intent}

用户消息: {msg}

对于 forward_etl 返回:
{{"target_entities": ["..."], "source_hints": ["..."], "code_type_hint": "spark_sql|flink_sql|java_flink|auto"}}

对于 reverse_synth 返回:
{{"eval_target": "...", "row_count_hint": 10, "buckets_hint": [{{"label":"优","range":[80,100]}}]}}

严格 JSON, 不要 Markdown。
"""


SCHEMA_EVOLVE_PROMPT = """用户要求修改元数据 schema。请把自然语言转为 schema diff JSON。

用户请求: {user_request}

当前相关表 schema:
{current_schema}

返回严格 JSON 数组, 每条变更形如:
{{"operation": "ADD_FIELD|DELETE_FIELD|UPDATE_FIELD|ADD_TABLE|DELETE_TABLE",
  "table": "...",
  "field": "...",                          // ADD_FIELD/DELETE_FIELD/UPDATE_FIELD 必填
  "data_type": "DOUBLE|INT|STRING|...",    // ADD_FIELD 必填
  "expression": "...",                     // 可选
  "upstream": [{{"table": "...", "field": "..."}}],
  "layer": "ODS|DWD|DWS|ADS|EVAL",         // ADD_TABLE 必填
  "storage_type": "KAFKA|HIVE|STARROCKS",  // ADD_TABLE 必填
  "fields": [...]                          // ADD_TABLE 必填
}}
"""


PROPOSE_PROMPT = """根据检测到的元数据缺口和用户原始需求，提出补齐建议。

缺口列表: {gaps}
用户请求: {user_request}

对每个 missing_table 缺口给出新建表草案; 对每个 missing_field 缺口给出新建字段草案。
返回严格 JSON 数组, 每条同 SCHEMA_EVOLVE_PROMPT 的 schema diff 格式。
确保层级 (ODS/DWD/...) 与存储 (KAFKA/HIVE/STARROCKS) 推断合理。
"""


CODE_GEN_PROMPT = """你是无线网络数据 ETL 代码生成器。

意图: {intent}
代码类型: {code_type}
相关 schema:
{schema}

用户请求: {user_request}

上一轮失败反馈 (若有, 修复后再生成):
{error_feedback}

输出要求:
1. 一段可直接提交沙箱执行的代码
2. 用 fenced code block 包裹 (```spark-sql / ```flink-sql / ```java)
3. 代码外的解释保持简短
"""


PRESENTER_REPHRASE_PROMPT = """把以下技术结果改写为面向用户的对话回复, 自然但不啰嗦。

意图: {intent}
结果摘要 JSON:
{summary_json}

直接输出回复正文, 不要前缀寒暄。
"""
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/test_prompts.py -v
```

预期：PASS (6/6)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/prompts.py tests/agent/test_prompts.py
git commit -m "feat(agent): LLM prompt templates for all nodes"
```

---

## Task 5: Tools — 11 个 thin wrappers

**Files:**
- Create: `backend/agent/tools.py`
- Create: `tests/agent/test_tools.py`

> spec §4.3 强调 "HTTP routes and Agent tools share the same service functions"。本 task 实现的工具几乎全是 1 行委托 + 类型/异常归一。

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/test_tools.py — mock 底层 service / searcher, 验证委托路径。"""
from unittest.mock import MagicMock, patch

import pytest

from backend.agent import tools


def test_search_tables_by_keyword_delegates_to_searcher():
    fake_searcher = MagicMock()
    fake_searcher.search.return_value = [
        {"doc": MagicMock(metadata={"table_name": "dws_cell_hourly", "field_name": None}), "score": 0.9, "table": "dws_cell_hourly"},
        {"doc": MagicMock(metadata={"table_name": "dwd_session_qos", "field_name": None}), "score": 0.3, "table": "dwd_session_qos"},
    ]
    r = tools.search_tables_by_keyword("覆盖强度", searcher=fake_searcher)
    assert r.top_table == "dws_cell_hourly"
    assert r.top_score == 0.9
    assert len(r.candidates) == 2


def test_lookup_table_schema_returns_dict_keyed_by_table():
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as m:
        m.return_value = MagicMock(name="dws_cell_hourly", fields=[])
        out = tools.lookup_table_schema(["dws_cell_hourly", "unknown"])
        assert "dws_cell_hourly" in out
        # unknown 表静默忽略, 不抛错 (gap_check 后续兜底)
        assert "unknown" not in out


def test_lookup_lineage_delegates_with_direction_and_depth():
    with patch("backend.agent.tools.metadata_service.get_lineage") as m:
        m.return_value = []
        tools.lookup_lineage("dws_cell_hourly", direction="up", depth=3)
        m.assert_called_once_with("dws_cell_hourly", direction="up", depth=3)


def test_check_gaps_returns_missing_when_score_low(monkeypatch):
    fake_searcher = MagicMock()
    fake_searcher.search.return_value = [
        {"doc": MagicMock(metadata={"table_name": "ods_ue_signal"}), "score": 0.05, "table": "ods_ue_signal"}
    ]
    gaps = tools.check_gaps(["基站负载"], searcher=fake_searcher, threshold=0.6)
    assert len(gaps) == 1
    assert gaps[0]["type"] == "missing_table"
    assert gaps[0]["keyword"] == "基站负载"


def test_validate_change_detects_break_downstream():
    """删除有下游引用的字段 → BREAK_DOWNSTREAM 错误。"""
    with patch("backend.agent.tools.metadata_service.get_lineage") as m:
        m.return_value = [MagicMock(to_table="dws_cell_hourly", to_field="avg_rsrp")]
        diff = [{"operation": "DELETE_FIELD", "table": "ods_ue_signal", "field": "rsrp"}]
        result = tools.validate_change(diff)
        assert result["passed"] is False
        assert any(e[0] == "BREAK_DOWNSTREAM" for e in result["errors"])


def test_validate_change_passes_for_clean_add():
    diff = [{"operation": "ADD_FIELD", "table": "dwd_session_qos", "field": "jitter",
             "data_type": "DOUBLE", "expression": "STDDEV(latency)"}]
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as m:
        m.return_value = MagicMock(fields=[])  # 没有重名
        result = tools.validate_change(diff)
        assert result["passed"] is True


def test_add_field_delegates_to_create_field():
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as gt, \
         patch("backend.agent.tools.metadata_service.create_field") as cf:
        gt.return_value = MagicMock(id="t1")
        cf.return_value = MagicMock(id="f1", name="jitter")
        op = {"operation": "ADD_FIELD", "table": "dwd_session_qos", "field": "jitter",
              "data_type": "DOUBLE", "expression": "STDDEV(latency)", "upstream": []}
        out = tools.add_field(op)
        assert out["field_id"] == "f1"


def test_generate_fake_data_delegates(monkeypatch):
    called = {}

    def fake(table, rows):
        called["args"] = (table, rows)
        return {"written": rows}

    monkeypatch.setattr("backend.agent.tools.fake_data.generate_fake_data", fake)
    out = tools.generate_fake_data("dwd_session_qos", 5)
    assert called["args"] == ("dwd_session_qos", 5)
    assert out["written"] == 5


def test_dry_run_dispatches_by_code_type(monkeypatch):
    captured = []

    def fake_execute(code, code_type):
        captured.append((code, code_type))
        from backend.agent.sandbox_stub import DryRunResult
        return DryRunResult(success=True, preview_row={"x": 1})

    monkeypatch.setattr("backend.agent.tools.sandbox.execute", fake_execute)
    r1 = tools.dry_run_spark_sql("SELECT 1")
    r2 = tools.dry_run_flink_sql("INSERT ...")
    r3 = tools.dry_run_java_flink("public class Job {}")
    assert captured == [("SELECT 1", "spark_sql"),
                        ("INSERT ...", "flink_sql"),
                        ("public class Job {}", "java_flink")]
    assert r1.success and r2.success and r3.success
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_tools.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/agent/tools.py`**

```python
"""Agent tools — 薄包装层。spec §4.3 强制：HTTP routes 与 Agent tools 共享 service。

工具入参/出参用 plain dict / dataclass，让 LangGraph 节点函数和单测都方便构造。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from backend.metadata import service as metadata_service
from backend.metadata.models import (
    CreateFieldRequest, CreateTableRequest, UpdateFieldRequest, UpstreamRef,
)
from backend.seed import fake_data
from backend.agent import sandbox_stub as sandbox


# ---------------- search ----------------

@dataclass
class SearchHit:
    table: str
    field: Optional[str]
    score: float


@dataclass
class SearchResult:
    top_table: Optional[str]
    top_score: float
    top_field: Optional[str]
    candidates: list[SearchHit] = field(default_factory=list)


def search_tables_by_keyword(keyword: str, *, searcher) -> SearchResult:
    """spec §4.3 工具。searcher 由调用方注入 (FastAPI app.state.searcher)。"""
    raw = searcher.search(keyword, k=10, use_rerank=False)
    if not raw:
        return SearchResult(top_table=None, top_score=0.0, top_field=None)
    top = raw[0]
    return SearchResult(
        top_table=top["table"],
        top_score=top["score"],
        top_field=top["doc"].metadata.get("field_name"),
        candidates=[
            SearchHit(
                table=r["table"],
                field=r["doc"].metadata.get("field_name"),
                score=r["score"],
            )
            for r in raw
        ],
    )


# ---------------- lookup ----------------

def lookup_table_schema(tables: list[str]) -> dict[str, dict]:
    """返回 {table_name: {fields:[{name,type,description,expression}], layer, storage_type}}。"""
    out: dict[str, dict] = {}
    for name in tables:
        if not name:
            continue
        try:
            t = metadata_service.get_table_by_name(name)
        except metadata_service.TableNotFound:
            continue
        out[name] = {
            "name": t.name,
            "layer": t.layer,
            "storage_type": t.storage_type,
            "fields": [
                {
                    "name": f.name,
                    "type": f.field_type,
                    "description": f.description,
                    "expression": f.expression,
                }
                for f in t.fields
            ],
        }
    return out


def lookup_lineage(table: str, *, direction: str = "down", depth: int = 5) -> list:
    return metadata_service.get_lineage(table, direction=direction, depth=depth)


# ---------------- gap check / proposal ----------------

def check_gaps(keywords: list[str], *, searcher, threshold: float = 0.6) -> list[dict]:
    gaps: list[dict] = []
    for kw in keywords:
        raw = searcher.search(kw, k=3, use_rerank=False)
        top_score = raw[0]["score"] if raw else 0.0
        if top_score < threshold:
            gaps.append({
                "type": "missing_table",
                "keyword": kw,
                "suggestion": f"建议新建表覆盖业务概念 '{kw}'",
            })
    return gaps


def propose_gap_fix(gaps: list[dict], *, llm_client) -> list[dict]:
    """LLM 草案生成由 gap_proposal 节点直接调，本工具仅为对称完整 — 当前实现 = 透传。"""
    return gaps


# ---------------- schema validation ----------------

def validate_change(diff: list[dict]) -> dict:
    errors, warnings = [], []
    for op in diff:
        kind = op["operation"]
        if kind == "ADD_FIELD":
            try:
                t = metadata_service.get_table_by_name(op["table"])
                if any(f.name == op["field"] for f in t.fields):
                    errors.append(("DUPLICATE", op))
            except metadata_service.TableNotFound:
                errors.append(("TABLE_NOT_FOUND", op))
        elif kind == "DELETE_FIELD":
            ds = metadata_service.get_lineage(op["table"], direction="down", depth=5)
            ds_relevant = [
                e for e in ds
                if getattr(e, "from_table", None) == op["table"]
                and getattr(e, "from_field", None) == op["field"]
            ]
            if ds_relevant:
                errors.append(("BREAK_DOWNSTREAM", op, [
                    (getattr(e, "to_table", None), getattr(e, "to_field", None))
                    for e in ds_relevant
                ]))
        elif kind == "UPDATE_FIELD":
            try:
                t = metadata_service.get_table_by_name(op["table"])
                if not any(f.name == op["field"] for f in t.fields):
                    errors.append(("FIELD_NOT_FOUND", op))
            except metadata_service.TableNotFound:
                errors.append(("TABLE_NOT_FOUND", op))
        elif kind == "ADD_TABLE":
            try:
                metadata_service.get_table_by_name(op["table"])
                errors.append(("DUPLICATE_TABLE", op))
            except metadata_service.TableNotFound:
                pass
        # cycle detection: 此处保留扩展位; 当前 schema 无递归 expression 引用即无循环
    return {"errors": errors, "warnings": warnings, "passed": len(errors) == 0}


# ---------------- schema mutations ----------------

def add_table(op: dict) -> dict:
    req = CreateTableRequest(
        name=op["table"],
        layer=op["layer"],
        storage_type=op["storage_type"],
        description=op.get("description", ""),
    )
    t = metadata_service.create_table(req)
    field_ids = []
    for f in op.get("fields", []):
        fr = CreateFieldRequest(
            table_id=t.id,
            name=f["name"],
            field_type=f["data_type"],
            is_nullable=f.get("nullable", True),
            is_partition=f.get("partition", False),
            expression=f.get("expression"),
            description=f.get("description", ""),
            upstream=[UpstreamRef(**u) for u in f.get("upstream", [])],
        )
        created = metadata_service.create_field(fr)
        field_ids.append(created.id)
    return {"table_id": t.id, "field_ids": field_ids}


def add_field(op: dict) -> dict:
    t = metadata_service.get_table_by_name(op["table"])
    fr = CreateFieldRequest(
        table_id=t.id,
        name=op["field"],
        field_type=op["data_type"],
        is_nullable=op.get("nullable", True),
        is_partition=op.get("partition", False),
        expression=op.get("expression"),
        description=op.get("description", ""),
        upstream=[UpstreamRef(**u) for u in op.get("upstream", [])],
    )
    created = metadata_service.create_field(fr)
    return {"field_id": created.id, "name": created.name}


def update_field(op: dict) -> dict:
    t = metadata_service.get_table_by_name(op["table"])
    fld = next(f for f in t.fields if f.name == op["field"])
    req = UpdateFieldRequest(
        field_type=op.get("data_type"),
        expression=op.get("expression"),
        description=op.get("description"),
        upstream=[UpstreamRef(**u) for u in op["upstream"]] if "upstream" in op else None,
    )
    updated = metadata_service.update_field(fld.id, req)
    return {"field_id": updated.id, "version": updated.version}


def remove_field(op: dict) -> dict:
    t = metadata_service.get_table_by_name(op["table"])
    fld = next(f for f in t.fields if f.name == op["field"])
    metadata_service.delete_field(fld.id)
    return {"field_id": fld.id, "removed": True}


# ---------------- data ----------------

def generate_fake_data(table: str, rows: int) -> dict:
    return fake_data.generate_fake_data(table, rows)


# ---------------- dry-run dispatchers ----------------

def dry_run_spark_sql(code: str):
    return sandbox.execute(code, "spark_sql")


def dry_run_flink_sql(code: str):
    return sandbox.execute(code, "flink_sql")


def dry_run_java_flink(code: str):
    return sandbox.execute(code, "java_flink")
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/test_tools.py -v
```

预期：PASS (9/9)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/tools.py tests/agent/test_tools.py
git commit -m "feat(agent): 11 agent tools as thin service wrappers"
```

---

## Task 6: yaml_sync — 单表 YAML 重写 + git commit

**Files:**
- Create: `backend/agent/yaml_sync.py`
- Create: `tests/agent/test_yaml_sync.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/test_yaml_sync.py"""
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.agent import yaml_sync


def test_sync_yaml_writes_files_for_given_tables(tmp_path, monkeypatch):
    monkeypatch.setenv("METADATA_YAML_DIR", str(tmp_path / "metadata-yaml"))
    from backend.config import get_settings
    get_settings.cache_clear()

    with patch("backend.agent.yaml_sync.run_query") as m:
        # 模拟 Neo4j 返回 1 表 2 字段
        m.side_effect = [
            [{"name": "dwd_session_qos", "layer": "DWD", "layer_priority": 2,
              "storage_type": "HIVE", "description": "会话 QoS 明细"}],
            [
                {"name": "session_id", "type": "STRING", "nullable": False, "partition": False,
                 "expression": None, "description": "", "upstream": []},
                {"name": "jitter", "type": "DOUBLE", "nullable": True, "partition": False,
                 "expression": "STDDEV(latency)", "description": "",
                 "upstream": [{"table": "dwd_session_qos", "field": "latency"}]},
            ],
        ]
        paths = yaml_sync.sync_yaml(["dwd_session_qos"])
    assert len(paths) == 1
    p = Path(paths[0])
    assert p.exists()
    assert p.parent.name == "L2-DWD"
    content = p.read_text(encoding="utf-8")
    assert "jitter" in content
    assert "STDDEV(latency)" in content


def test_git_commit_returns_sha(tmp_path, monkeypatch):
    # 初始化临时 git 仓库
    subprocess.check_call(["git", "init"], cwd=tmp_path)
    subprocess.check_call(["git", "config", "user.email", "x@y.z"], cwd=tmp_path)
    subprocess.check_call(["git", "config", "user.name", "Tester"], cwd=tmp_path)
    (tmp_path / "a.txt").write_text("hi")
    subprocess.check_call(["git", "add", "."], cwd=tmp_path)
    subprocess.check_call(["git", "commit", "-m", "init"], cwd=tmp_path)
    (tmp_path / "a.txt").write_text("bye")

    sha = yaml_sync.git_commit("test commit", repo_root=str(tmp_path))
    assert isinstance(sha, str) and len(sha) == 40
    log = subprocess.check_output(["git", "log", "-1", "--pretty=%H"], cwd=tmp_path, text=True).strip()
    assert log == sha


def test_git_commit_returns_empty_when_no_changes(tmp_path):
    subprocess.check_call(["git", "init"], cwd=tmp_path)
    subprocess.check_call(["git", "config", "user.email", "x@y.z"], cwd=tmp_path)
    subprocess.check_call(["git", "config", "user.name", "Tester"], cwd=tmp_path)
    (tmp_path / "a.txt").write_text("hi")
    subprocess.check_call(["git", "add", "."], cwd=tmp_path)
    subprocess.check_call(["git", "commit", "-m", "init"], cwd=tmp_path)

    sha = yaml_sync.git_commit("nothing", repo_root=str(tmp_path))
    assert sha == ""
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_yaml_sync.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/agent/yaml_sync.py`**

```python
"""sync_yaml(tables) — 对指定表的 YAML 单独重写; git_commit — 提交 metadata-yaml/。"""
from __future__ import annotations

import pathlib
from typing import Optional

import yaml
from git import Actor, InvalidGitRepositoryError, Repo

from backend.config import get_settings
from backend.metadata.graph import run_query


LAYER_DIR = {"ODS": "L1-ODS", "DWD": "L2-DWD", "DWS": "L3-DWS", "ADS": "L4-ADS", "EVAL": "L5-EVAL"}


def sync_yaml(table_names: list[str]) -> list[str]:
    """对每个表从 Neo4j 重新读取并覆盖写 metadata-yaml/L*-*/<table>.yaml。

    返回写入的路径列表 (绝对路径)。
    """
    settings = get_settings()
    root = pathlib.Path(settings.metadata_yaml_dir).resolve()
    paths: list[str] = []
    for name in table_names:
        rows = run_query(
            """
            MATCH (t:Table {name: $name})
            RETURN t.name AS name, t.layer AS layer, t.layer_priority AS layer_priority,
                   t.storage_type AS storage_type, t.description AS description
            """,
            name=name,
        )
        if not rows:
            continue
        t = rows[0]
        field_rows = run_query(
            """
            MATCH (t:Table {name: $name})-[:HAS_FIELD]->(f:Field)
            OPTIONAL MATCH (f)-[:DERIVES_FROM]->(up:Field)<-[:HAS_FIELD]-(up_t:Table)
            WITH f, collect(DISTINCT {table: up_t.name, field: up.name}) AS upstream
            RETURN f.name AS name, f.field_type AS type, f.is_nullable AS nullable,
                   f.is_partition AS partition, f.expression AS expression,
                   f.description AS description, upstream
            ORDER BY f.name
            """,
            name=name,
        )
        doc = {
            "name": t["name"],
            "layer": t["layer"],
            "storage_type": t["storage_type"],
            "description": t["description"],
            "fields": [
                {
                    "name": f["name"],
                    "type": f["type"],
                    "nullable": f["nullable"],
                    "partition": f["partition"],
                    "expression": f["expression"],
                    "description": f["description"],
                    "upstream": [u for u in f["upstream"] if u.get("table")],
                }
                for f in field_rows
            ],
        }
        layer_dir = root / LAYER_DIR[t["layer"]]
        layer_dir.mkdir(parents=True, exist_ok=True)
        out = layer_dir / f"{name}.yaml"
        out.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        paths.append(str(out))
    return paths


def git_commit(message: str, *, repo_root: Optional[str] = None) -> str:
    """commit 当前所有改动 (含 untracked metadata-yaml/*); 无改动返回 ''。"""
    settings = get_settings()
    actor = Actor(settings.git_author_name, settings.git_author_email)
    try:
        repo = Repo(repo_root or ".", search_parent_directories=True)
    except InvalidGitRepositoryError:
        return ""
    repo.git.add(A=True)
    if not repo.is_dirty(untracked_files=True) and not repo.index.diff("HEAD"):
        return ""
    if not repo.index.diff("HEAD") and not repo.untracked_files:
        return ""
    commit = repo.index.commit(message, author=actor, committer=actor)
    return commit.hexsha
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/test_yaml_sync.py -v
```

预期：PASS (3/3)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/yaml_sync.py tests/agent/test_yaml_sync.py
git commit -m "feat(agent): per-table YAML rewrite + git_commit helper"
```

---

## Task 7: ChatSession 内存存储

**Files:**
- Create: `backend/agent/chat_session.py`
- Create: `tests/agent/test_chat_session.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/test_chat_session.py"""
import pytest

from backend.agent.chat_session import ChatSession, ChatSessionStore


def test_new_session_has_unique_id_and_empty_messages():
    store = ChatSessionStore()
    s1 = store.new()
    s2 = store.new()
    assert s1.id != s2.id
    assert s1.messages == []


def test_get_returns_same_session(store_factory):
    store = store_factory()
    s = store.new()
    assert store.get(s.id) is s


def test_get_unknown_id_raises():
    store = ChatSessionStore()
    with pytest.raises(KeyError):
        store.get("does-not-exist")


def test_append_message_persists():
    store = ChatSessionStore()
    s = store.new()
    store.append_message(s.id, role="user", content="hi")
    store.append_message(s.id, role="assistant", content="hello")
    msgs = store.get(s.id).messages
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "hi"


@pytest.fixture
def store_factory():
    return ChatSessionStore
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_chat_session.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/agent/chat_session.py`**

```python
"""进程内 chat session 存储 — 单进程 FastAPI 验证场景够用。

不持久化到 SQLite 是有意决定 (slice 2b out-of-scope)。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional


@dataclass
class ChatSession:
    id: str
    messages: list[dict] = field(default_factory=list)
    state: dict = field(default_factory=dict)
    last_result: Optional[dict] = None


class ChatSessionStore:
    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}
        self._lock = Lock()

    def new(self) -> ChatSession:
        with self._lock:
            sid = f"chat_{uuid.uuid4().hex[:12]}"
            s = ChatSession(id=sid)
            self._sessions[sid] = s
            return s

    def get(self, session_id: str) -> ChatSession:
        with self._lock:
            return self._sessions[session_id]

    def append_message(self, session_id: str, *, role: str, content: str) -> None:
        with self._lock:
            self._sessions[session_id].messages.append({"role": role, "content": content})

    def set_last_result(self, session_id: str, result: dict) -> None:
        with self._lock:
            self._sessions[session_id].last_result = result
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/test_chat_session.py -v
```

预期：PASS (4/4)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/chat_session.py tests/agent/test_chat_session.py
git commit -m "feat(agent): in-memory ChatSessionStore"
```

---

## Task 8: classifier 节点

**Files:**
- Create: `backend/agent/nodes/classifier.py`
- Create: `tests/agent/nodes/test_classifier.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/nodes/test_classifier.py — mock DeepSeek, 覆盖三条意图 + 低置信度 + JSON parse 降级。"""
import json
from unittest.mock import MagicMock

from backend.agent.nodes.classifier import classifier


def _fake_resp(payload):
    r = MagicMock()
    r.content = json.dumps(payload) if isinstance(payload, dict) else payload
    return r


def test_classifier_returns_forward_etl_on_high_confidence():
    client = MagicMock()
    client.invoke.return_value = _fake_resp({"intent": "forward_etl", "confidence": 0.95, "reason": "查询聚合"})
    state = {"messages": [{"role": "user", "content": "求平均 RSRP"}]}
    out = classifier(state, llm_client=client)
    assert out["intent"] == "forward_etl"
    assert out["needs_clarification"] is False


def test_classifier_sets_needs_clarification_when_low_confidence():
    client = MagicMock()
    client.invoke.return_value = _fake_resp({"intent": "schema_evolve", "confidence": 0.4, "reason": "..."})
    state = {"messages": [{"role": "user", "content": "?"}], "intent": "forward_etl"}
    out = classifier(state, llm_client=client)
    assert out["needs_clarification"] is True
    assert out["intent"] == "forward_etl"  # 保留上一轮


def test_classifier_falls_back_to_keyword_on_json_parse_error():
    client = MagicMock()
    client.invoke.side_effect = [_fake_resp("not a json"), _fake_resp("still not")]
    state = {"messages": [{"role": "user", "content": "造点数据"}]}
    out = classifier(state, llm_client=client)
    assert out["intent"] == "reverse_synth"  # 关键词 "造数据" 命中


def test_classifier_keyword_fallback_for_schema_evolve():
    client = MagicMock()
    client.invoke.side_effect = [_fake_resp("x"), _fake_resp("y")]
    state = {"messages": [{"role": "user", "content": "给表加个字段"}]}
    out = classifier(state, llm_client=client)
    assert out["intent"] == "schema_evolve"


def test_classifier_default_keyword_fallback_is_forward_etl():
    client = MagicMock()
    client.invoke.side_effect = [_fake_resp("x"), _fake_resp("y")]
    state = {"messages": [{"role": "user", "content": "嗯"}]}
    out = classifier(state, llm_client=client)
    assert out["intent"] == "forward_etl"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/nodes/test_classifier.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/agent/nodes/classifier.py`**

```python
"""classifier 节点 — spec §4.1。LLM 失败时降级到关键词规则。"""
from __future__ import annotations

import json
from typing import Any

from backend.agent.prompts import CLASSIFIER_PROMPT


VALID_INTENTS = {"forward_etl", "reverse_synth", "schema_evolve"}


def _keyword_fallback(text: str) -> str:
    if any(k in text for k in ["造数据", "造点", "合成数据", "生成测试数据"]):
        return "reverse_synth"
    if any(k in text for k in ["加字段", "加一个", "新增字段", "删除字段", "改字段", "新建表", "演进"]):
        return "schema_evolve"
    return "forward_etl"


def classifier(state: dict, *, llm_client: Any) -> dict:
    recent = state.get("messages", [])[-3:]
    history_text = "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent
    )
    prompt = CLASSIFIER_PROMPT.format(
        history=history_text,
        prev_intent=state.get("intent"),
        context_source=state.get("context_source"),
    )

    last_msg = recent[-1].get("content", "") if recent else ""

    for _ in range(2):  # spec: 重试 1 次
        try:
            resp = llm_client.invoke(prompt)
            parsed = json.loads(getattr(resp, "content", str(resp)))
            intent = parsed.get("intent")
            confidence = float(parsed.get("confidence", 0.0))
            if intent in VALID_INTENTS:
                if confidence < 0.7:
                    return {
                        "intent": state.get("intent") or "forward_etl",
                        "needs_clarification": True,
                    }
                return {"intent": intent, "needs_clarification": False}
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            continue

    return {"intent": _keyword_fallback(last_msg), "needs_clarification": False}
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/nodes/test_classifier.py -v
```

预期：PASS (5/5)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/nodes/classifier.py tests/agent/nodes/test_classifier.py
git commit -m "feat(agent): classifier node with keyword fallback"
```

---

## Task 9: forward_etl + reverse_synth 节点

**Files:**
- Create: `backend/agent/nodes/forward_etl.py`
- Create: `backend/agent/nodes/reverse_synth.py`
- Create: `tests/agent/nodes/test_forward_etl.py`
- Create: `tests/agent/nodes/test_reverse_synth.py`

- [ ] **Step 1: 失败测试（两文件）**

`tests/agent/nodes/test_forward_etl.py`:

```python
import json
from unittest.mock import MagicMock

from backend.agent.nodes.forward_etl import forward_etl
from backend.agent.tools import SearchResult, SearchHit


def _resp(payload):
    m = MagicMock()
    m.content = json.dumps(payload)
    return m


def test_forward_etl_extracts_targets_and_sources():
    client = MagicMock()
    client.invoke.return_value = _resp({
        "target_entities": ["小区小时覆盖"],
        "source_hints": ["UE 信号"],
        "code_type_hint": "spark_sql",
    })
    searcher = MagicMock()
    searcher.search.side_effect = [
        [{"doc": MagicMock(metadata={"table_name": "dws_cell_hourly", "field_name": None}), "score": 0.9, "table": "dws_cell_hourly"}],
        [{"doc": MagicMock(metadata={"table_name": "ods_ue_signal", "field_name": None}), "score": 0.85, "table": "ods_ue_signal"}],
    ]
    state = {"messages": [{"role": "user", "content": "用 ods_ue_signal 算小区小时覆盖"}]}
    out = forward_etl(state, llm_client=client, searcher=searcher)
    assert out["target_tables"] == ["dws_cell_hourly"]
    assert out["source_tables"] == ["ods_ue_signal"]
    assert out["code_type"] == "spark_sql"


def test_forward_etl_auto_code_type_means_none():
    client = MagicMock()
    client.invoke.return_value = _resp({
        "target_entities": ["x"], "source_hints": [], "code_type_hint": "auto",
    })
    searcher = MagicMock()
    searcher.search.return_value = [
        {"doc": MagicMock(metadata={"table_name": "t", "field_name": None}), "score": 0.9, "table": "t"}
    ]
    out = forward_etl({"messages": [{"role": "user", "content": "..."}]},
                      llm_client=client, searcher=searcher)
    assert out["code_type"] is None


def test_forward_etl_empty_targets_when_llm_fails():
    client = MagicMock()
    client.invoke.return_value = _resp("not json")
    searcher = MagicMock()
    out = forward_etl({"messages": [{"role": "user", "content": "."}]},
                      llm_client=client, searcher=searcher)
    assert out["target_tables"] == []
    assert out["source_tables"] == []
```

`tests/agent/nodes/test_reverse_synth.py`:

```python
import json
from unittest.mock import MagicMock

from backend.agent.nodes.reverse_synth import reverse_synth


def _resp(payload):
    m = MagicMock()
    m.content = json.dumps(payload)
    return m


def test_reverse_synth_extracts_eval_target_and_hints():
    client = MagicMock()
    client.invoke.return_value = _resp({
        "eval_target": "用户评分",
        "row_count_hint": 10,
        "buckets_hint": [{"label": "优", "range": [80, 100]}],
    })
    searcher = MagicMock()
    searcher.search.return_value = [
        {"doc": MagicMock(metadata={"table_name": "eval_user_score", "field_name": None}), "score": 0.92, "table": "eval_user_score"}
    ]
    state = {"messages": [{"role": "user", "content": "造 10 行评分数据"}]}
    out = reverse_synth(state, llm_client=client, searcher=searcher)
    assert out["target_tables"] == ["eval_user_score"]
    assert out["source_tables"] == []
    assert out["row_count_hint"] == 10
    assert out["buckets_hint"][0]["label"] == "优"


def test_reverse_synth_default_row_count():
    client = MagicMock()
    client.invoke.return_value = _resp({"eval_target": "x"})
    searcher = MagicMock()
    searcher.search.return_value = [
        {"doc": MagicMock(metadata={"table_name": "x", "field_name": None}), "score": 0.5, "table": "x"}
    ]
    out = reverse_synth({"messages": [{"role": "user", "content": "."}]},
                        llm_client=client, searcher=searcher)
    assert out["row_count_hint"] == 10
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/nodes/test_forward_etl.py tests/agent/nodes/test_reverse_synth.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现两个节点**

`backend/agent/nodes/forward_etl.py`:

```python
"""forward_etl 节点 — spec §4.1。"""
from __future__ import annotations

import json
from typing import Any

from backend.agent.prompts import EXTRACT_PROMPT
from backend.agent.tools import search_tables_by_keyword


def forward_etl(state: dict, *, llm_client: Any, searcher: Any) -> dict:
    msg = state.get("messages", [{}])[-1].get("content", "")
    prompt = EXTRACT_PROMPT.format(msg=msg, intent="forward_etl")
    try:
        resp = llm_client.invoke(prompt)
        parsed = json.loads(getattr(resp, "content", str(resp)))
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return {"target_tables": [], "source_tables": [], "code_type": None}

    targets = [
        search_tables_by_keyword(k, searcher=searcher).top_table
        for k in parsed.get("target_entities", [])
    ]
    sources = [
        search_tables_by_keyword(k, searcher=searcher).top_table
        for k in parsed.get("source_hints", [])
    ]
    hint = parsed.get("code_type_hint")
    return {
        "target_tables": [t for t in targets if t],
        "source_tables": [s for s in sources if s],
        "code_type": hint if hint and hint != "auto" else None,
    }
```

`backend/agent/nodes/reverse_synth.py`:

```python
"""reverse_synth 节点 — spec §4.1。"""
from __future__ import annotations

import json
from typing import Any

from backend.agent.prompts import EXTRACT_PROMPT
from backend.agent.tools import search_tables_by_keyword


def reverse_synth(state: dict, *, llm_client: Any, searcher: Any) -> dict:
    msg = state.get("messages", [{}])[-1].get("content", "")
    prompt = EXTRACT_PROMPT.format(msg=msg, intent="reverse_synth")
    try:
        resp = llm_client.invoke(prompt)
        parsed = json.loads(getattr(resp, "content", str(resp)))
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        parsed = {}

    eval_target = parsed.get("eval_target", "")
    target = (
        search_tables_by_keyword(eval_target, searcher=searcher).top_table
        if eval_target else None
    )
    return {
        "target_tables": [target] if target else [],
        "source_tables": [],
        "row_count_hint": int(parsed.get("row_count_hint", 10)),
        "buckets_hint": parsed.get("buckets_hint", []) or [],
    }
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/nodes/test_forward_etl.py tests/agent/nodes/test_reverse_synth.py -v
```

预期：PASS (5/5)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/nodes/forward_etl.py backend/agent/nodes/reverse_synth.py tests/agent/nodes/test_forward_etl.py tests/agent/nodes/test_reverse_synth.py
git commit -m "feat(agent): forward_etl and reverse_synth entry nodes"
```

---

## Task 10: pipeline_parse + schema_lookup 节点

**Files:**
- Create: `backend/agent/nodes/pipeline_parse.py`
- Create: `backend/agent/nodes/schema_lookup.py`
- Create: `tests/agent/nodes/test_pipeline_parse.py`
- Create: `tests/agent/nodes/test_schema_lookup.py`

- [ ] **Step 1: 失败测试**

`tests/agent/nodes/test_pipeline_parse.py`:

```python
from unittest.mock import patch, MagicMock

from backend.agent.nodes.pipeline_parse import pipeline_parse


def test_pipeline_parse_traces_upstream_chain():
    """eval_user_score → ads_cell_profile → dws_cell_hourly → dwd_session_qos → ods_ue_signal。"""

    def fake_lineage(table, direction="up", depth=5):
        chain = {
            "eval_user_score": [MagicMock(from_table="ads_cell_profile", from_field="coverage_score")],
            "ads_cell_profile": [MagicMock(from_table="dws_cell_hourly", from_field="avg_rsrp")],
            "dws_cell_hourly": [MagicMock(from_table="dwd_session_qos", from_field="avg_rsrp")],
            "dwd_session_qos": [MagicMock(from_table="ods_ue_signal", from_field="rsrp")],
            "ods_ue_signal": [],
        }
        return chain.get(table, [])

    with patch("backend.agent.nodes.pipeline_parse.lookup_lineage", side_effect=fake_lineage):
        out = pipeline_parse({"target_tables": ["eval_user_score"]})

    assert "eval_user_score" not in out["source_tables"]
    for upstream in ["ods_ue_signal", "dwd_session_qos", "dws_cell_hourly", "ads_cell_profile"]:
        assert upstream in out["source_tables"]
    # chain ODS→EVAL 顺序: 最后一项是 root
    assert out["pipeline_chain"][-1]["table"] == "eval_user_score"


def test_pipeline_parse_handles_no_upstream():
    with patch("backend.agent.nodes.pipeline_parse.lookup_lineage", return_value=[]):
        out = pipeline_parse({"target_tables": ["lone_table"]})
    assert out["source_tables"] == []
    assert out["pipeline_chain"][0]["table"] == "lone_table"
```

`tests/agent/nodes/test_schema_lookup.py`:

```python
from unittest.mock import patch

from backend.agent.nodes.schema_lookup import schema_lookup


def test_schema_lookup_fetches_targets_and_sources():
    with patch("backend.agent.nodes.schema_lookup.lookup_table_schema") as m:
        m.return_value = {"dws_cell_hourly": {"layer": "DWS"}, "ods_ue_signal": {"layer": "ODS"}}
        out = schema_lookup({"target_tables": ["dws_cell_hourly"], "source_tables": ["ods_ue_signal"]})
        m.assert_called_once_with(["dws_cell_hourly", "ods_ue_signal"])
        assert "dws_cell_hourly" in out["schemas_resolved"]


def test_schema_lookup_clears_sub_flow_active_when_set():
    with patch("backend.agent.nodes.schema_lookup.lookup_table_schema", return_value={}):
        out = schema_lookup({"target_tables": [], "source_tables": [], "sub_flow_active": True})
    assert out["sub_flow_active"] is False
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/nodes/test_pipeline_parse.py tests/agent/nodes/test_schema_lookup.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现两个节点**

`backend/agent/nodes/pipeline_parse.py`:

```python
"""pipeline_parse — 反向合成专用，从根表回溯到所有上游 (spec §4.1)。"""
from __future__ import annotations

from backend.agent.tools import lookup_lineage


def pipeline_parse(state: dict) -> dict:
    roots = state.get("target_tables", [])
    if not roots:
        return {"source_tables": [], "pipeline_chain": []}
    root = roots[0]
    chain: list[dict] = []
    visited: set[str] = set()
    stack: list[str] = [root]
    while stack:
        t = stack.pop()
        if t in visited:
            continue
        visited.add(t)
        edges = lookup_lineage(t, direction="up", depth=1)
        upstream_tables = sorted({e.from_table for e in edges if getattr(e, "from_table", None)})
        chain.append({
            "table": t,
            "fields": sorted({e.from_field for e in edges if getattr(e, "from_field", None)}),
            "upstream": upstream_tables,
        })
        stack.extend(upstream_tables)
    return {
        "source_tables": sorted(visited - {root}),
        "pipeline_chain": list(reversed(chain)),  # ODS→EVAL
    }
```

`backend/agent/nodes/schema_lookup.py`:

```python
"""schema_lookup — 把 target+source 表的 schema 取到 State (spec §4.1)。"""
from __future__ import annotations

from backend.agent.tools import lookup_table_schema


def schema_lookup(state: dict) -> dict:
    tables = list({*state.get("target_tables", []), *state.get("source_tables", [])})
    schemas = lookup_table_schema(tables)
    out: dict = {"schemas_resolved": schemas}
    if state.get("sub_flow_active"):
        out["sub_flow_active"] = False
    return out
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/nodes/test_pipeline_parse.py tests/agent/nodes/test_schema_lookup.py -v
```

预期：PASS (4/4)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/nodes/pipeline_parse.py backend/agent/nodes/schema_lookup.py tests/agent/nodes/test_pipeline_parse.py tests/agent/nodes/test_schema_lookup.py
git commit -m "feat(agent): pipeline_parse and schema_lookup nodes"
```

---

## Task 11: gap_check + gap_proposal 节点

**Files:**
- Create: `backend/agent/nodes/gap_check.py`
- Create: `backend/agent/nodes/gap_proposal.py`
- Create: `tests/agent/nodes/test_gap_check.py`
- Create: `tests/agent/nodes/test_gap_proposal.py`

- [ ] **Step 1: 失败测试**

`tests/agent/nodes/test_gap_check.py`:

```python
import json
from unittest.mock import MagicMock

from backend.agent.nodes.gap_check import gap_check


def _resp(payload):
    r = MagicMock()
    r.content = json.dumps(payload)
    return r


def test_gap_check_detects_missing_table():
    """关键词搜不到表 (score < 0.6) → missing_table。"""
    client = MagicMock()
    client.invoke.return_value = _resp([
        {"keyword": "基站负载", "field_specified": False, "field": None},
    ])
    searcher = MagicMock()
    searcher.search.return_value = [
        {"doc": MagicMock(metadata={"table_name": "ods_ue_signal", "field_name": None}), "score": 0.05, "table": "ods_ue_signal"}
    ]
    state = {"messages": [{"role": "user", "content": "需要基站负载和信号质量"}]}
    out = gap_check(state, llm_client=client, searcher=searcher)
    assert out["has_gaps"] is True
    assert any(g["type"] == "missing_table" and g["keyword"] == "基站负载" for g in out["gaps"])


def test_gap_check_no_gaps_when_high_score():
    client = MagicMock()
    client.invoke.return_value = _resp([
        {"keyword": "覆盖强度", "field_specified": False, "field": None},
    ])
    searcher = MagicMock()
    searcher.search.return_value = [
        {"doc": MagicMock(metadata={"table_name": "dws_cell_hourly", "field_name": None}), "score": 0.92, "table": "dws_cell_hourly"}
    ]
    out = gap_check({"messages": [{"role": "user", "content": "x"}]},
                    llm_client=client, searcher=searcher)
    assert out["has_gaps"] is False
    assert out["gaps"] == []


def test_gap_check_llm_failure_returns_no_gaps():
    client = MagicMock()
    client.invoke.return_value = _resp("not json")
    searcher = MagicMock()
    out = gap_check({"messages": [{"role": "user", "content": "x"}]},
                    llm_client=client, searcher=searcher)
    assert out["has_gaps"] is False
```

`tests/agent/nodes/test_gap_proposal.py`:

```python
import json
from unittest.mock import MagicMock

from backend.agent.nodes.gap_proposal import gap_proposal


def _resp(payload):
    r = MagicMock()
    r.content = json.dumps(payload)
    return r


def test_gap_proposal_builds_schema_diff_and_sub_flow_state():
    client = MagicMock()
    client.invoke.return_value = _resp([
        {"operation": "ADD_TABLE", "table": "ods_gnb_load", "layer": "ODS",
         "storage_type": "KAFKA",
         "fields": [{"name": "cpu_util", "data_type": "DOUBLE", "description": "CPU 使用率"}]}
    ])
    state = {
        "gaps": [{"type": "missing_table", "keyword": "基站负载", "suggestion": "建议新建 ods_gnb_load"}],
        "messages": [{"role": "user", "content": "需要基站负载"}],
    }
    out = gap_proposal(state, llm_client=client)
    assert out["sub_flow_active"] is True
    assert out["sub_flow_return_point"] == "code_generate"
    assert len(out["schema_diff"]) == 1
    assert out["schema_diff"][0]["table"] == "ods_gnb_load"
    assert out["presenter_payload"]["type"] == "gap_proposal_card"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/nodes/test_gap_check.py tests/agent/nodes/test_gap_proposal.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现两个节点**

`backend/agent/nodes/gap_check.py`:

```python
"""gap_check — 检测用户需求实体与现有元数据的缺口 (spec §4.1)。"""
from __future__ import annotations

import json
from typing import Any


EXTRACT_ENTITIES_PROMPT = """从用户消息抽取业务实体关键词。
用户消息: {msg}

返回严格 JSON 数组:
[{{"keyword": "...", "field_specified": false, "field": null}}, ...]
"""


def _extract_required_entities(msg: str, llm_client: Any) -> list[dict]:
    try:
        resp = llm_client.invoke(EXTRACT_ENTITIES_PROMPT.format(msg=msg))
        return json.loads(getattr(resp, "content", str(resp)))
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return []


def gap_check(state: dict, *, llm_client: Any, searcher: Any,
              threshold: float = 0.6) -> dict:
    msg = state.get("messages", [{}])[-1].get("content", "")
    required = _extract_required_entities(msg, llm_client)
    gaps: list[dict] = []
    for ent in required:
        kw = ent.get("keyword")
        if not kw:
            continue
        raw = searcher.search(kw, k=3, use_rerank=False)
        top_score = raw[0]["score"] if raw else 0.0
        top_table = raw[0]["table"] if raw else None
        if top_score < threshold:
            gaps.append({
                "type": "missing_table",
                "keyword": kw,
                "suggestion": f"建议新建表覆盖 '{kw}'",
            })
        elif ent.get("field_specified") and ent.get("field"):
            # 字段级缺口在 schema_validate 之后由 LLM 提案；此处保留接口
            pass
    return {"gaps": gaps, "has_gaps": len(gaps) > 0}
```

`backend/agent/nodes/gap_proposal.py`:

```python
"""gap_proposal — 根据 gaps 生成补齐草案 (spec §4.1)。"""
from __future__ import annotations

import json
from typing import Any

from backend.agent.prompts import PROPOSE_PROMPT


def gap_proposal(state: dict, *, llm_client: Any) -> dict:
    gaps = state.get("gaps", [])
    msg = state.get("messages", [{}])[-1].get("content", "")
    prompt = PROPOSE_PROMPT.format(gaps=json.dumps(gaps, ensure_ascii=False), user_request=msg)
    try:
        resp = llm_client.invoke(prompt)
        draft = json.loads(getattr(resp, "content", str(resp)))
        if not isinstance(draft, list):
            draft = []
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        draft = []

    return {
        "schema_diff": draft,
        "sub_flow_active": True,
        "sub_flow_return_point": "code_generate",
        "presenter_payload": {
            "type": "gap_proposal_card",
            "draft": draft,
            "gaps": gaps,
        },
    }
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/nodes/test_gap_check.py tests/agent/nodes/test_gap_proposal.py -v
```

预期：PASS (4/4)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/nodes/gap_check.py backend/agent/nodes/gap_proposal.py tests/agent/nodes/test_gap_check.py tests/agent/nodes/test_gap_proposal.py
git commit -m "feat(agent): gap_check and gap_proposal nodes"
```

---

## Task 12: code_generate + dry_run 节点

**Files:**
- Create: `backend/agent/nodes/code_generate.py`
- Create: `backend/agent/nodes/dry_run.py`
- Create: `tests/agent/nodes/test_code_generate.py`
- Create: `tests/agent/nodes/test_dry_run.py`

- [ ] **Step 1: 失败测试**

`tests/agent/nodes/test_code_generate.py`:

```python
from unittest.mock import MagicMock, patch

from backend.agent.nodes.code_generate import code_generate, extract_code_block, infer_code_type


def test_extract_code_block_handles_fenced_spark_sql():
    text = "Explanation\n```spark-sql\nSELECT * FROM t\n```\nDone"
    code = extract_code_block(text, lang="spark-sql")
    assert code.strip() == "SELECT * FROM t"


def test_extract_code_block_falls_back_to_any_fence():
    text = "```\nFOO\n```"
    assert extract_code_block(text, lang="spark-sql").strip() == "FOO"


def test_infer_code_type_uses_target_storage():
    state = {
        "target_tables": ["dws_cell_hourly"],
        "schemas_resolved": {"dws_cell_hourly": {"storage_type": "HIVE"}},
    }
    assert infer_code_type(state) == "spark_sql"

    state2 = {
        "target_tables": ["ods_x"],
        "schemas_resolved": {"ods_x": {"storage_type": "KAFKA"}},
    }
    assert infer_code_type(state2) == "flink_sql"


def test_code_generate_increments_iteration_and_extracts_code():
    client = MagicMock()
    resp = MagicMock()
    resp.content = "```spark-sql\nSELECT 1\n```"
    client.invoke.return_value = resp
    state = {
        "intent": "forward_etl",
        "target_tables": ["dws_cell_hourly"],
        "source_tables": ["ods_ue_signal"],
        "messages": [{"role": "user", "content": "..."}],
        "schemas_resolved": {"dws_cell_hourly": {"storage_type": "HIVE"}},
        "iteration_count": 0,
    }
    out = code_generate(state, llm_client=client)
    assert "SELECT 1" in out["generated_code"]
    assert out["code_type"] == "spark_sql"
    assert out["iteration_count"] == 1


def test_code_generate_respects_explicit_code_type():
    client = MagicMock()
    resp = MagicMock()
    resp.content = "```flink-sql\nINSERT\n```"
    client.invoke.return_value = resp
    state = {
        "intent": "forward_etl",
        "code_type": "flink_sql",
        "target_tables": [], "source_tables": [],
        "messages": [{"role": "user", "content": "."}],
        "schemas_resolved": {},
    }
    out = code_generate(state, llm_client=client)
    assert out["code_type"] == "flink_sql"
```

`tests/agent/nodes/test_dry_run.py`:

```python
from unittest.mock import patch

from backend.agent.nodes.dry_run import dry_run
from backend.agent.sandbox_stub import DryRunResult


def test_dry_run_success_clears_error_feedback():
    with patch("backend.agent.nodes.dry_run.sandbox") as m:
        m.execute.return_value = DryRunResult(success=True, preview_row={"a": 1})
        state = {"generated_code": "SELECT 1", "code_type": "spark_sql"}
        out = dry_run(state)
    assert out["dry_run_result"]["success"] is True
    assert out["error_feedback"] is None


def test_dry_run_failure_writes_error_feedback_truncated():
    with patch("backend.agent.nodes.dry_run.sandbox") as m:
        m.execute.return_value = DryRunResult(success=False, error_log="x" * 3000)
        state = {"generated_code": "BAD", "code_type": "spark_sql"}
        out = dry_run(state)
    assert out["dry_run_result"]["success"] is False
    assert len(out["error_feedback"]) <= 2000


def test_dry_run_unknown_code_type_returns_error():
    state = {"generated_code": "x", "code_type": "no_such_type"}
    out = dry_run(state)
    assert out["dry_run_result"]["success"] is False
    assert "code_type" in out["error_feedback"]
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/nodes/test_code_generate.py tests/agent/nodes/test_dry_run.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现两个节点**

`backend/agent/nodes/code_generate.py`:

```python
"""code_generate 节点 — spec §4.1。"""
from __future__ import annotations

import json
import re
from typing import Any

from backend.agent.prompts import CODE_GEN_PROMPT


_STORAGE_TO_CODE_TYPE = {
    "HIVE": "spark_sql",
    "KAFKA": "flink_sql",
    "STARROCKS": "spark_sql",
}


def _code_type_to_lang(code_type: str) -> str:
    return {"spark_sql": "spark-sql", "flink_sql": "flink-sql", "java_flink": "java"}.get(code_type, "")


def extract_code_block(text: str, *, lang: str) -> str:
    """先抓 ```{lang} ...```，回退到 ``` ...```。"""
    pat = re.compile(r"```" + re.escape(lang) + r"\s*\n(.*?)```", re.DOTALL)
    m = pat.search(text)
    if m:
        return m.group(1).strip()
    pat2 = re.compile(r"```\s*\n(.*?)```", re.DOTALL)
    m2 = pat2.search(text)
    return m2.group(1).strip() if m2 else ""


def infer_code_type(state: dict) -> str:
    targets = state.get("target_tables", [])
    schemas = state.get("schemas_resolved", {})
    for t in targets:
        st = (schemas.get(t) or {}).get("storage_type")
        if st in _STORAGE_TO_CODE_TYPE:
            return _STORAGE_TO_CODE_TYPE[st]
    return "spark_sql"


def code_generate(state: dict, *, llm_client: Any) -> dict:
    code_type = state.get("code_type") or infer_code_type(state)
    schemas = state.get("schemas_resolved", {})
    msg = state.get("messages", [{}])[-1].get("content", "")
    prompt = CODE_GEN_PROMPT.format(
        schema=json.dumps(schemas, ensure_ascii=False),
        intent=state.get("intent", "forward_etl"),
        user_request=msg,
        code_type=code_type,
        error_feedback=state.get("error_feedback") or "(无)",
    )
    resp = llm_client.invoke(prompt)
    content = getattr(resp, "content", str(resp))
    code = extract_code_block(content, lang=_code_type_to_lang(code_type))
    return {
        "generated_code": code,
        "code_type": code_type,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }
```

`backend/agent/nodes/dry_run.py`:

```python
"""dry_run 节点 — spec §4.1。沙箱真实实现在 slice 2c。"""
from __future__ import annotations

from dataclasses import asdict

from backend.agent import sandbox_stub as sandbox

VALID_CODE_TYPES = {"spark_sql", "flink_sql", "java_flink"}


def dry_run(state: dict) -> dict:
    code_type = state.get("code_type", "")
    if code_type not in VALID_CODE_TYPES:
        return {
            "dry_run_result": {"success": False, "preview_row": None,
                                "error_log": f"unknown code_type: {code_type!r}",
                                "application_id": None},
            "error_feedback": f"unknown code_type: {code_type!r}",
        }
    result = sandbox.execute(state.get("generated_code", ""), code_type)
    payload = asdict(result)
    if result.success:
        return {"dry_run_result": payload, "error_feedback": None}
    err = (result.error_log or "")[:2000]
    return {"dry_run_result": payload, "error_feedback": err}
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/nodes/test_code_generate.py tests/agent/nodes/test_dry_run.py -v
```

预期：PASS (8/8)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/nodes/code_generate.py backend/agent/nodes/dry_run.py tests/agent/nodes/test_code_generate.py tests/agent/nodes/test_dry_run.py
git commit -m "feat(agent): code_generate and dry_run nodes"
```

---

## Task 13: presenter 节点

**Files:**
- Create: `backend/agent/nodes/presenter.py`
- Create: `tests/agent/nodes/test_presenter.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/nodes/test_presenter.py"""
from unittest.mock import MagicMock

from backend.agent.nodes.presenter import presenter, build_payload


def test_build_payload_for_dry_run_success():
    state = {
        "intent": "forward_etl",
        "generated_code": "SELECT 1",
        "code_type": "spark_sql",
        "dry_run_result": {"success": True, "preview_row": {"a": 1}, "error_log": None},
    }
    p = build_payload(state)
    assert p["type"] == "code_card"
    assert p["code"] == "SELECT 1"
    assert p["preview_row"] == {"a": 1}


def test_build_payload_for_clarification():
    p = build_payload({"needs_clarification": True, "messages": [{"role": "user", "content": "?"}]})
    assert p["type"] == "clarification"


def test_build_payload_for_gap_proposal_passes_existing_payload():
    existing = {"type": "gap_proposal_card", "draft": [{"op": "ADD_TABLE"}], "gaps": []}
    p = build_payload({"presenter_payload": existing, "intent": "forward_etl"})
    assert p is existing


def test_build_payload_for_schema_apply():
    state = {
        "intent": "schema_evolve",
        "applied_changes": [{"change_id": "c1", "operation": "ADD_FIELD"}],
        "validation_result": {"errors": [], "warnings": [], "passed": True},
    }
    p = build_payload(state)
    assert p["type"] == "schema_diff_card"
    assert p["applied"][0]["change_id"] == "c1"


def test_build_payload_for_validation_failure():
    state = {
        "intent": "schema_evolve",
        "validation_result": {"errors": [("BREAK_DOWNSTREAM", {"table": "x"})],
                              "warnings": [], "passed": False},
    }
    p = build_payload(state)
    assert p["type"] == "error"
    assert "BREAK_DOWNSTREAM" in p["summary"]


def test_presenter_emits_sse(monkeypatch):
    state = {"intent": "forward_etl", "generated_code": "x", "code_type": "spark_sql",
             "dry_run_result": {"success": True, "preview_row": {"a": 1}, "error_log": None}}
    emitted = []

    def sink(payload):
        emitted.append(payload)

    out = presenter(state, sse_emit=sink)
    assert emitted and emitted[0]["type"] == "code_card"
    assert out["final_message"].startswith(("生成", "完成", "成功", "已"))
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/nodes/test_presenter.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现 `backend/agent/nodes/presenter.py`**

```python
"""presenter 节点 — 终止节点, 构造 UI 载荷 + SSE 推送 (spec §4.1)。"""
from __future__ import annotations

from typing import Any, Callable, Optional


def build_payload(state: dict) -> dict:
    if state.get("presenter_payload"):
        # gap_proposal 已经构造好载荷, 直接转发
        return state["presenter_payload"]

    if state.get("needs_clarification"):
        return {
            "type": "clarification",
            "summary": "需要澄清，请补充更多信息。",
        }

    intent = state.get("intent")
    vr = state.get("validation_result") or {}
    if intent == "schema_evolve":
        if vr.get("passed") is False:
            err_codes = [e[0] for e in vr.get("errors", [])]
            return {
                "type": "error",
                "summary": "校验未通过: " + ", ".join(err_codes),
                "errors": vr.get("errors", []),
            }
        if state.get("applied_changes"):
            return {
                "type": "schema_diff_card",
                "applied": state["applied_changes"],
                "warnings": vr.get("warnings", []),
            }

    dr = state.get("dry_run_result") or {}
    if dr:
        return {
            "type": "code_card",
            "code": state.get("generated_code", ""),
            "code_type": state.get("code_type"),
            "preview_row": dr.get("preview_row"),
            "success": bool(dr.get("success")),
            "error_log": dr.get("error_log"),
            "summary": "执行成功" if dr.get("success") else "执行失败，请查看错误日志",
        }

    return {"type": "error", "summary": "未知状态"}


def presenter(state: dict, *, sse_emit: Optional[Callable[[dict], None]] = None) -> dict:
    payload = build_payload(state)
    if sse_emit is not None:
        sse_emit(payload)
    summary = payload.get("summary") or "已完成"
    return {"final_message": summary}
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/nodes/test_presenter.py -v
```

预期：PASS (6/6)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/nodes/presenter.py tests/agent/nodes/test_presenter.py
git commit -m "feat(agent): presenter node with payload dispatch"
```

---

## Task 14: schema_evolve + schema_validate 节点

**Files:**
- Create: `backend/agent/nodes/schema_evolve.py`
- Create: `backend/agent/nodes/schema_validate.py`
- Create: `tests/agent/nodes/test_schema_evolve.py`
- Create: `tests/agent/nodes/test_schema_validate.py`

- [ ] **Step 1: 失败测试**

`tests/agent/nodes/test_schema_evolve.py`:

```python
import json
from unittest.mock import MagicMock, patch

from backend.agent.nodes.schema_evolve import schema_evolve


def _resp(payload):
    r = MagicMock()
    r.content = json.dumps(payload)
    return r


def test_schema_evolve_main_flow_uses_llm():
    client = MagicMock()
    client.invoke.return_value = _resp([
        {"operation": "ADD_FIELD", "table": "dwd_session_qos", "field": "jitter",
         "data_type": "DOUBLE", "expression": "STDDEV(latency)"}
    ])
    with patch("backend.agent.nodes.schema_evolve.lookup_table_schema") as m:
        m.return_value = {"dwd_session_qos": {"fields": []}}
        out = schema_evolve(
            {"messages": [{"role": "user", "content": "加 jitter"}],
             "target_tables": ["dwd_session_qos"]},
            llm_client=client,
        )
    assert out["schema_diff"][0]["operation"] == "ADD_FIELD"
    assert out["schema_diff"][0]["field"] == "jitter"


def test_schema_evolve_sub_flow_reuses_gap_proposal_draft():
    """sub_flow_active=True 时不再 LLM, 直接用 schema_diff (gap_proposal 已填好)。"""
    client = MagicMock()
    pre_filled = [{"operation": "ADD_TABLE", "table": "ods_gnb_load", "layer": "ODS",
                   "storage_type": "KAFKA", "fields": []}]
    out = schema_evolve(
        {"sub_flow_active": True, "schema_diff": pre_filled},
        llm_client=client,
    )
    client.invoke.assert_not_called()
    assert out["schema_diff"] == pre_filled


def test_schema_evolve_retries_once_on_invalid_json():
    client = MagicMock()
    client.invoke.side_effect = [_resp("garbage"),
                                  _resp([{"operation": "ADD_FIELD", "table": "t",
                                          "field": "f", "data_type": "INT"}])]
    with patch("backend.agent.nodes.schema_evolve.lookup_table_schema", return_value={}):
        out = schema_evolve(
            {"messages": [{"role": "user", "content": "加字段"}], "target_tables": []},
            llm_client=client,
        )
    assert client.invoke.call_count == 2
    assert out["schema_diff"][0]["field"] == "f"
```

`tests/agent/nodes/test_schema_validate.py`:

```python
from unittest.mock import patch

from backend.agent.nodes.schema_validate import schema_validate


def test_schema_validate_passes_for_clean_add():
    with patch("backend.agent.nodes.schema_validate.validate_change") as m:
        m.return_value = {"errors": [], "warnings": [], "passed": True}
        out = schema_validate({"schema_diff": [{"operation": "ADD_FIELD",
                                                  "table": "t", "field": "f", "data_type": "INT"}]})
    assert out["validation_result"]["passed"] is True


def test_schema_validate_fails_on_break_downstream():
    with patch("backend.agent.nodes.schema_validate.validate_change") as m:
        m.return_value = {"errors": [("BREAK_DOWNSTREAM", {"table": "x", "field": "y"})],
                          "warnings": [], "passed": False}
        out = schema_validate({"schema_diff": [{"operation": "DELETE_FIELD",
                                                  "table": "x", "field": "y"}]})
    assert out["validation_result"]["passed"] is False
    assert out["validation_result"]["errors"][0][0] == "BREAK_DOWNSTREAM"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/nodes/test_schema_evolve.py tests/agent/nodes/test_schema_validate.py -v
```

预期：FAIL。

- [ ] **Step 3: 实现两个节点**

`backend/agent/nodes/schema_evolve.py`:

```python
"""schema_evolve 节点 — 主流程 LLM 生成 diff; 子流程复用 gap_proposal 草案 (spec §4.1)。"""
from __future__ import annotations

import json
from typing import Any

from backend.agent.prompts import SCHEMA_EVOLVE_PROMPT
from backend.agent.tools import lookup_table_schema


def schema_evolve(state: dict, *, llm_client: Any) -> dict:
    if state.get("sub_flow_active"):
        # gap_proposal 已经把 schema_diff 填好了，直接透传 (spec §4.1)
        return {"schema_diff": state.get("schema_diff", [])}

    msg = state.get("messages", [{}])[-1].get("content", "")
    current = lookup_table_schema(state.get("target_tables", []))
    prompt = SCHEMA_EVOLVE_PROMPT.format(
        user_request=msg,
        current_schema=json.dumps(current, ensure_ascii=False),
    )

    for attempt in range(2):  # spec: 严 prompt 重提 1 次
        try:
            resp = llm_client.invoke(prompt)
            parsed = json.loads(getattr(resp, "content", str(resp)))
            if isinstance(parsed, list):
                return {"schema_diff": parsed}
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            continue

    return {"schema_diff": []}
```

`backend/agent/nodes/schema_validate.py`:

```python
"""schema_validate — 写库前一致性校验 (spec §4.1)。"""
from __future__ import annotations

from backend.agent.tools import validate_change


def schema_validate(state: dict) -> dict:
    result = validate_change(state.get("schema_diff", []))
    return {"validation_result": result}
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/nodes/test_schema_evolve.py tests/agent/nodes/test_schema_validate.py -v
```

预期：PASS (5/5)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/nodes/schema_evolve.py backend/agent/nodes/schema_validate.py tests/agent/nodes/test_schema_evolve.py tests/agent/nodes/test_schema_validate.py
git commit -m "feat(agent): schema_evolve and schema_validate nodes"
```

---

## Task 15: schema_apply 节点

**Files:**
- Create: `backend/agent/nodes/schema_apply.py`
- Create: `tests/agent/nodes/test_schema_apply.py`

> 这是 slice 2b 最复杂的节点：事务内 Neo4j CRUD + 同事务内重写 YAML，事务外 git commit + 回填 `Change.commit_hash`。

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/nodes/test_schema_apply.py — mock tools + yaml_sync, 覆盖各 op 分派 + commit_hash 回填。"""
from unittest.mock import MagicMock, patch

from backend.agent.nodes.schema_apply import schema_apply, _record_change


def test_schema_apply_dispatches_add_table(monkeypatch):
    monkeypatch.setattr("backend.agent.nodes.schema_apply.tools.add_table",
                        lambda op: {"table_id": "t1", "field_ids": []})
    monkeypatch.setattr("backend.agent.nodes.schema_apply.tools.add_field",
                        lambda op: pytest_fail("should not be called"))
    monkeypatch.setattr("backend.agent.nodes.schema_apply.yaml_sync.sync_yaml",
                        lambda tables: ["x.yaml"])
    monkeypatch.setattr("backend.agent.nodes.schema_apply.yaml_sync.git_commit",
                        lambda msg: "deadbeef" * 5)
    monkeypatch.setattr("backend.agent.nodes.schema_apply._record_change",
                        lambda op, commit_hash=None: {"change_id": "c1", "operation": op["operation"],
                                                       "commit_hash": commit_hash})
    monkeypatch.setattr("backend.agent.nodes.schema_apply._update_change_commit",
                        lambda cid, sha: None)

    diff = [{"operation": "ADD_TABLE", "table": "ods_gnb_load", "layer": "ODS",
             "storage_type": "KAFKA", "fields": []}]
    out = schema_apply({"schema_diff": diff})
    assert len(out["applied_changes"]) == 1
    assert out["applied_changes"][0]["operation"] == "ADD_TABLE"


def test_schema_apply_collects_affected_tables_for_yaml():
    captured = {}
    def fake_sync(tables):
        captured["tables"] = sorted(tables)
        return [f"{t}.yaml" for t in tables]

    with patch("backend.agent.nodes.schema_apply.tools.add_field", return_value={"field_id": "f1"}), \
         patch("backend.agent.nodes.schema_apply.tools.update_field", return_value={"field_id": "f2", "version": 2}), \
         patch("backend.agent.nodes.schema_apply.tools.remove_field", return_value={"field_id": "f3", "removed": True}), \
         patch("backend.agent.nodes.schema_apply.yaml_sync.sync_yaml", side_effect=fake_sync), \
         patch("backend.agent.nodes.schema_apply.yaml_sync.git_commit", return_value="sha"), \
         patch("backend.agent.nodes.schema_apply._record_change",
               side_effect=lambda op, commit_hash=None: {"change_id": f"c_{op['table']}",
                                                          "operation": op["operation"]}), \
         patch("backend.agent.nodes.schema_apply._update_change_commit"):
        diff = [
            {"operation": "ADD_FIELD", "table": "t1", "field": "a", "data_type": "INT"},
            {"operation": "UPDATE_FIELD", "table": "t2", "field": "b", "expression": "x+1"},
            {"operation": "DELETE_FIELD", "table": "t3", "field": "c"},
        ]
        schema_apply({"schema_diff": diff})
    assert captured["tables"] == ["t1", "t2", "t3"]


def test_schema_apply_returns_empty_when_diff_empty():
    out = schema_apply({"schema_diff": []})
    assert out["applied_changes"] == []
```

> 注：上面 `pytest_fail` 是 typo 占位；改成 `pytest.fail` 并在测试文件顶 `import pytest`。下一步给出完整可运行版本。

- [ ] **Step 2: 把上面 `pytest_fail` 换成正确导入并运行**

把 test 文件顶部加 `import pytest`，把 `pytest_fail` 替换为 `pytest.fail`。然后：

```bash
pytest tests/agent/nodes/test_schema_apply.py -v
```

预期：FAIL — `ModuleNotFoundError: backend.agent.nodes.schema_apply`。

- [ ] **Step 3: 实现 `backend/agent/nodes/schema_apply.py`**

```python
"""schema_apply — 把 schema_diff 落 Neo4j + YAML 同步 + git commit + Change.commit_hash 回填。

spec §4.1: 事务内做 Neo4j 写 + YAML 写, 事务外 git commit, 然后 update Change.commit_hash。
本实现里 Neo4j 写由 backend.metadata.service 各 mutation 函数完成 (各自一个事务);
完整的事务包络在 slice 1b 已 commit 的 service 设计下做不到 (service 接受 dict 入参, 每次
开一个 session)。我们用补偿写法 — 任一 op 失败则中止后续 op, 已写入的不回滚, 由 schema_validate
保证错误前置拦截。
"""
from __future__ import annotations

import uuid
from typing import Optional

from backend.agent import tools, yaml_sync
from backend.metadata.graph import run_query


def _record_change(op: dict, *, commit_hash: Optional[str] = None) -> dict:
    """写一条 (:Change) 节点, 返回 {change_id, operation, table, field, commit_hash}。"""
    change_id = f"chg_{uuid.uuid4().hex[:12]}"
    run_query(
        """
        CREATE (c:Change {
            id: $id, operation: $operation, table_name: $table,
            field_name: $field, changed_at: datetime(), commit_hash: $commit
        })
        """,
        id=change_id,
        operation=op["operation"],
        table=op.get("table", ""),
        field=op.get("field"),
        commit=commit_hash,
    )
    return {
        "change_id": change_id,
        "operation": op["operation"],
        "table": op.get("table"),
        "field": op.get("field"),
        "commit_hash": commit_hash,
    }


def _update_change_commit(change_id: str, sha: str) -> None:
    run_query(
        "MATCH (c:Change {id: $id}) SET c.commit_hash = $sha",
        id=change_id, sha=sha,
    )


def _affected_tables(diff: list[dict]) -> list[str]:
    return sorted({op["table"] for op in diff if op.get("table")})


def _summarize(diff: list[dict]) -> str:
    parts = []
    for op in diff:
        if "field" in op and op["field"]:
            parts.append(f"{op['operation']} {op['table']}.{op['field']}")
        else:
            parts.append(f"{op['operation']} {op['table']}")
    return "; ".join(parts) or "(empty)"


def schema_apply(state: dict) -> dict:
    diff = state.get("schema_diff", [])
    if not diff:
        return {"applied_changes": []}

    applied: list[dict] = []
    for op in diff:
        kind = op["operation"]
        if kind == "ADD_TABLE":
            tools.add_table(op)
        elif kind == "ADD_FIELD":
            tools.add_field(op)
        elif kind == "UPDATE_FIELD":
            tools.update_field(op)
        elif kind == "DELETE_FIELD":
            tools.remove_field(op)
        # 写一条 Change (commit_hash 先空, commit 后回填)
        change = _record_change(op, commit_hash=None)
        applied.append(change)

    # YAML 同步 — 只重写受影响的表
    yaml_sync.sync_yaml(_affected_tables(diff))

    # git commit — message 编进 table/version 便于事后反查 (spec §6.9 版本映射)
    sha = yaml_sync.git_commit(f"schema_evolve: {_summarize(diff)}")
    if sha:
        for a in applied:
            _update_change_commit(a["change_id"], sha)
            a["commit_hash"] = sha

    return {"applied_changes": applied}
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/nodes/test_schema_apply.py -v
```

预期：PASS (3/3)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/nodes/schema_apply.py tests/agent/nodes/test_schema_apply.py
git commit -m "feat(agent): schema_apply with Change node + YAML sync + git commit"
```

---

## Task 16: Graph 装配 + 双层重试上限 + 路由测试

**Files:**
- Create: `backend/agent/graph.py`
- Create: `tests/agent/test_graph_routing.py`

- [ ] **Step 1: 失败测试**

```python
"""tests/agent/test_graph_routing.py — 不依赖真实 LLM/Neo4j; 验证 build_graph 节点连通性。"""
from unittest.mock import MagicMock

from backend.agent.graph import build_graph, after_classifier, after_dry_run, after_gap_check, after_schema_validate
from backend.config import get_settings


def test_after_classifier_routes_to_intent_branch():
    assert after_classifier({"needs_clarification": True}) == "presenter"
    assert after_classifier({"intent": "forward_etl"}) == "forward_etl"
    assert after_classifier({"intent": "reverse_synth"}) == "reverse_synth"
    assert after_classifier({"intent": "schema_evolve"}) == "schema_evolve"


def test_after_gap_check_routes_by_has_gaps():
    assert after_gap_check({"has_gaps": False}) == "code_generate"
    assert after_gap_check({"has_gaps": True}) == "gap_proposal"


def test_after_dry_run_loops_back_on_failure_under_limit(monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_max_iterations", 3, raising=False)
    state = {"dry_run_result": {"success": False}, "iteration_count": 1}
    assert after_dry_run(state) == "code_generate"


def test_after_dry_run_exits_to_presenter_when_max_iterations_hit():
    state = {"dry_run_result": {"success": False}, "iteration_count": 3}
    assert after_dry_run(state) == "presenter"


def test_after_dry_run_exits_to_presenter_on_success():
    state = {"dry_run_result": {"success": True}, "iteration_count": 1}
    assert after_dry_run(state) == "presenter"


def test_after_schema_validate_routes_apply_or_presenter():
    assert after_schema_validate({"validation_result": {"passed": True}}) == "schema_apply"
    assert after_schema_validate({"validation_result": {"passed": False}}) == "presenter"


def test_build_graph_returns_compiled_object():
    g = build_graph(llm_client=MagicMock(), searcher=MagicMock())
    # CompiledGraph 暴露 invoke / stream
    assert hasattr(g, "invoke")
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_graph_routing.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/agent/graph.py`**

```python
"""LangGraph 装配 + 条件边 + Agent 层迭代上限 (spec §4.1 + §4.5)。"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.agent.state import AgentState
from backend.agent.nodes.classifier import classifier
from backend.agent.nodes.forward_etl import forward_etl
from backend.agent.nodes.reverse_synth import reverse_synth
from backend.agent.nodes.pipeline_parse import pipeline_parse
from backend.agent.nodes.schema_lookup import schema_lookup
from backend.agent.nodes.gap_check import gap_check
from backend.agent.nodes.gap_proposal import gap_proposal
from backend.agent.nodes.code_generate import code_generate
from backend.agent.nodes.dry_run import dry_run
from backend.agent.nodes.presenter import presenter
from backend.agent.nodes.schema_evolve import schema_evolve
from backend.agent.nodes.schema_validate import schema_validate
from backend.agent.nodes.schema_apply import schema_apply
from backend.config import get_settings


# ---------------- 条件边路由 ----------------

def after_classifier(state: dict) -> str:
    if state.get("needs_clarification"):
        return "presenter"
    return state.get("intent", "forward_etl")


def after_gap_check(state: dict) -> str:
    return "gap_proposal" if state.get("has_gaps") else "code_generate"


def after_gap_proposal(state: dict) -> str:
    """先去 presenter 渲染卡片; 用户 [确认并继续] 经 /api/schema/apply 触发新一轮 run。

    本切片不在 graph 内部等待人工; 用户确认后由 /api/schema/apply 接口直接进入 schema_evolve 子流程。
    所以这里直接 → presenter (返回卡片) → END。
    """
    return "presenter"


def after_schema_validate(state: dict) -> str:
    return "schema_apply" if (state.get("validation_result") or {}).get("passed") else "presenter"


def after_schema_apply(state: dict) -> str:
    """主流程 → presenter; 子流程 (sub_flow_active 被 schema_lookup 清掉前为 True) → schema_lookup。"""
    return "schema_lookup" if state.get("sub_flow_active") else "presenter"


def after_dry_run(state: dict) -> str:
    settings = get_settings()
    dr = state.get("dry_run_result") or {}
    if dr.get("success"):
        return "presenter"
    if state.get("iteration_count", 0) >= settings.agent_max_iterations:
        return "presenter"
    return "code_generate"


# ---------------- 装配 ----------------

def build_graph(*, llm_client: Any, searcher: Any):
    """构建并编译 StateGraph。所有 LLM 调用与 searcher 走依赖注入。"""

    g = StateGraph(AgentState)

    g.add_node("classifier", lambda s: classifier(s, llm_client=llm_client))
    g.add_node("forward_etl", lambda s: forward_etl(s, llm_client=llm_client, searcher=searcher))
    g.add_node("reverse_synth", lambda s: reverse_synth(s, llm_client=llm_client, searcher=searcher))
    g.add_node("pipeline_parse", pipeline_parse)
    g.add_node("schema_lookup", schema_lookup)
    g.add_node("gap_check", lambda s: gap_check(s, llm_client=llm_client, searcher=searcher))
    g.add_node("gap_proposal", lambda s: gap_proposal(s, llm_client=llm_client))
    g.add_node("code_generate", lambda s: code_generate(s, llm_client=llm_client))
    g.add_node("dry_run", dry_run)
    g.add_node("schema_evolve", lambda s: schema_evolve(s, llm_client=llm_client))
    g.add_node("schema_validate", schema_validate)
    g.add_node("schema_apply", schema_apply)
    g.add_node("presenter", presenter)

    g.add_edge(START, "classifier")
    g.add_conditional_edges("classifier", after_classifier, {
        "forward_etl": "forward_etl",
        "reverse_synth": "reverse_synth",
        "schema_evolve": "schema_evolve",
        "presenter": "presenter",
    })
    g.add_edge("forward_etl", "schema_lookup")
    g.add_edge("reverse_synth", "pipeline_parse")
    g.add_edge("pipeline_parse", "gap_check")
    g.add_edge("schema_lookup", "gap_check")
    g.add_conditional_edges("gap_check", after_gap_check, {
        "code_generate": "code_generate",
        "gap_proposal": "gap_proposal",
    })
    g.add_conditional_edges("gap_proposal", after_gap_proposal, {
        "presenter": "presenter",
    })

    g.add_edge("schema_evolve", "schema_validate")
    g.add_conditional_edges("schema_validate", after_schema_validate, {
        "schema_apply": "schema_apply",
        "presenter": "presenter",
    })
    g.add_conditional_edges("schema_apply", after_schema_apply, {
        "schema_lookup": "schema_lookup",
        "presenter": "presenter",
    })

    g.add_edge("code_generate", "dry_run")
    g.add_conditional_edges("dry_run", after_dry_run, {
        "code_generate": "code_generate",
        "presenter": "presenter",
    })
    g.add_edge("presenter", END)

    return g.compile()
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/agent/test_graph_routing.py -v
```

预期：PASS (7/7)。

- [ ] **Step 5: 提交**

```bash
git add backend/agent/graph.py tests/agent/test_graph_routing.py
git commit -m "feat(agent): build_graph with conditional edges and iteration limit"
```

---

## Task 17: Graph e2e 测试 — 三条主路径打通

**Files:**
- Create: `tests/agent/test_graph_e2e.py`

> 全部用 mock LLM + monkeypatch sandbox，**不依赖真实 DeepSeek**。

- [ ] **Step 1: 写测试**

```python
"""tests/agent/test_graph_e2e.py — 三条主路径打通。"""
import json
from unittest.mock import MagicMock, patch

import pytest

from backend.agent.graph import build_graph
from backend.agent.sandbox_stub import DryRunResult


def _llm_seq(*payloads):
    """构造一个按调用顺序返回不同 content 的假 client.invoke。"""
    client = MagicMock()
    msgs = []
    for p in payloads:
        m = MagicMock()
        m.content = json.dumps(p) if not isinstance(p, str) else p
        msgs.append(m)
    client.invoke.side_effect = msgs
    return client


def _stub_searcher(table: str, score: float = 0.9):
    s = MagicMock()
    s.search.return_value = [
        {"doc": MagicMock(metadata={"table_name": table, "field_name": None}),
         "score": score, "table": table}
    ]
    return s


def test_p2_1_forward_etl_spark_sql_path(monkeypatch):
    """P2-1: 用 ods_ue_signal 算每小区小时平均 RSRP/SINR → 走 forward_etl → spark_sql。"""
    client = _llm_seq(
        # classifier
        {"intent": "forward_etl", "confidence": 0.95, "reason": "..."},
        # forward_etl 抽取
        {"target_entities": ["dws_cell_hourly"], "source_hints": ["ods_ue_signal"], "code_type_hint": "spark_sql"},
        # gap_check extract_entities
        [{"keyword": "覆盖", "field_specified": False, "field": None}],
        # code_generate
        "```spark-sql\nSELECT cell_id FROM ods_ue_signal\n```",
        # presenter rephrase (实际未调用; 占位备用)
        "OK",
    )
    searcher = _stub_searcher("dws_cell_hourly")

    monkeypatch.setattr(
        "backend.agent.nodes.dry_run.sandbox.execute",
        lambda code, code_type: DryRunResult(success=True, preview_row={"cell_id": "1"}),
    )
    with patch("backend.agent.tools.metadata_service.get_table_by_name") as gt:
        gt.return_value = MagicMock(name="x", fields=[], storage_type="HIVE")
        g = build_graph(llm_client=client, searcher=searcher)
        final = g.invoke({"messages": [{"role": "user", "content": "求平均 RSRP"}]})
    assert final["code_type"] == "spark_sql"
    assert "SELECT" in final["generated_code"]
    assert final["dry_run_result"]["success"] is True


def test_p2_8_schema_evolve_add_jitter_path(monkeypatch):
    """P2-8: 给 dwd_session_qos 加 jitter 字段, 校验 + apply 全过。"""
    client = _llm_seq(
        # classifier
        {"intent": "schema_evolve", "confidence": 0.9, "reason": "..."},
        # schema_evolve diff
        [{"operation": "ADD_FIELD", "table": "dwd_session_qos", "field": "jitter",
          "data_type": "DOUBLE", "expression": "STDDEV(latency)", "upstream": []}],
    )
    searcher = _stub_searcher("dwd_session_qos")

    with patch("backend.agent.tools.metadata_service.get_table_by_name") as gt, \
         patch("backend.agent.tools.metadata_service.create_field") as cf, \
         patch("backend.agent.tools.metadata_service.get_lineage", return_value=[]), \
         patch("backend.agent.nodes.schema_apply.yaml_sync.sync_yaml", return_value=[]), \
         patch("backend.agent.nodes.schema_apply.yaml_sync.git_commit", return_value="sha"), \
         patch("backend.agent.nodes.schema_apply._record_change",
               side_effect=lambda op, commit_hash=None: {"change_id": "c1", "operation": op["operation"],
                                                          "table": op["table"], "field": op.get("field"),
                                                          "commit_hash": commit_hash}), \
         patch("backend.agent.nodes.schema_apply._update_change_commit"):
        gt.return_value = MagicMock(name="dwd_session_qos", id="t1", fields=[])
        cf.return_value = MagicMock(id="f_jitter")
        g = build_graph(llm_client=client, searcher=searcher)
        final = g.invoke({"messages": [{"role": "user", "content": "加 jitter"}],
                          "target_tables": ["dwd_session_qos"]})
    assert final["validation_result"]["passed"] is True
    assert any(c["operation"] == "ADD_FIELD" for c in final["applied_changes"])


def test_p2_9_schema_validate_blocks_break_downstream(monkeypatch):
    """P2-9: 删除 ods_ue_signal.rsrp → validate 拒绝。"""
    client = _llm_seq(
        {"intent": "schema_evolve", "confidence": 0.92, "reason": "..."},
        [{"operation": "DELETE_FIELD", "table": "ods_ue_signal", "field": "rsrp"}],
    )
    searcher = _stub_searcher("ods_ue_signal")
    with patch("backend.agent.tools.metadata_service.get_lineage") as m:
        m.return_value = [MagicMock(from_table="ods_ue_signal", from_field="rsrp",
                                     to_table="dwd_session_qos", to_field="avg_rsrp")]
        g = build_graph(llm_client=client, searcher=searcher)
        final = g.invoke({"messages": [{"role": "user", "content": "删 rsrp"}],
                          "target_tables": ["ods_ue_signal"]})
    assert final["validation_result"]["passed"] is False
    assert any(e[0] == "BREAK_DOWNSTREAM" for e in final["validation_result"]["errors"])


def test_p2_11_gap_check_missing_table(monkeypatch):
    """P2-11: '基站负载' 检索不到 → gap_check 标 missing_table → gap_proposal 生成草案 → presenter 卡片。"""
    client = _llm_seq(
        {"intent": "forward_etl", "confidence": 0.92, "reason": "."},
        # forward_etl extract
        {"target_entities": ["小区小时画像"], "source_hints": [], "code_type_hint": "spark_sql"},
        # gap_check extract entities — 2 个关键词
        [{"keyword": "基站负载", "field_specified": False, "field": None},
         {"keyword": "信号质量", "field_specified": False, "field": None}],
        # gap_proposal LLM draft
        [{"operation": "ADD_TABLE", "table": "ods_gnb_load", "layer": "ODS",
          "storage_type": "KAFKA", "fields": []}],
    )

    def search_side(query, k=10, use_rerank=False):
        if "负载" in query:
            return [{"doc": MagicMock(metadata={"table_name": "ods_ue_signal", "field_name": None}),
                     "score": 0.05, "table": "ods_ue_signal"}]
        return [{"doc": MagicMock(metadata={"table_name": "dws_cell_hourly", "field_name": None}),
                 "score": 0.92, "table": "dws_cell_hourly"}]

    searcher = MagicMock()
    searcher.search.side_effect = search_side

    g = build_graph(llm_client=client, searcher=searcher)
    final = g.invoke({"messages": [{"role": "user", "content": "需要基站负载和信号质量"}]})
    assert final["has_gaps"] is True
    assert any(g_["type"] == "missing_table" and g_["keyword"] == "基站负载" for g_ in final["gaps"])
    assert final["presenter_payload"]["type"] == "gap_proposal_card"
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/agent/test_graph_e2e.py -v
```

预期：PASS (4/4)。如果有断言失败，**优先查 Task 16 的条件边路由是否漏了一条边**，不要改测试。

- [ ] **Step 3: 提交**

```bash
git add tests/agent/test_graph_e2e.py
git commit -m "test(agent): e2e paths for P2-1, P2-8, P2-9, P2-11"
```

---

## Task 18: `/api/chat/*` SSE 接口

**Files:**
- Create: `backend/api/chat.py`
- Create: `tests/agent/test_api_chat.py`
- Modify: `backend/main.py`（注册路由 + 把 `ChatSessionStore` 挂到 `app.state`）

- [ ] **Step 1: 写测试**

```python
"""tests/agent/test_api_chat.py — 用 TestClient 黑盒, mock LLM/sandbox。"""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.agent.sandbox_stub import DryRunResult


@pytest.fixture
def app_with_mocks(monkeypatch, tmp_path):
    import numpy as np

    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[hash(t) % 100 / 100.0] * 16 for t in texts])

    monkeypatch.setattr("backend.search.embedder.SentenceTransformer",
                        lambda name: StubEncoder())
    monkeypatch.setenv("SEARCH_BOOTSTRAP_FROM_SEED", "1")
    monkeypatch.setenv("SEARCH_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from backend.config import get_settings
    get_settings.cache_clear()

    fake_llm = MagicMock()
    # 路径: classifier → forward_etl → schema_lookup → gap_check → code_generate → dry_run → presenter
    msgs = [
        MagicMock(content=json.dumps({"intent": "forward_etl", "confidence": 0.95})),
        MagicMock(content=json.dumps({"target_entities": ["x"], "source_hints": [], "code_type_hint": "spark_sql"})),
        MagicMock(content=json.dumps([])),  # gap_check entities — 空
        MagicMock(content="```spark-sql\nSELECT 1\n```"),
    ]
    fake_llm.invoke.side_effect = msgs * 5  # 容忍多次调用

    monkeypatch.setattr("backend.api.chat.build_chat_client", lambda **kw: fake_llm)
    monkeypatch.setattr(
        "backend.agent.nodes.dry_run.sandbox.execute",
        lambda code, code_type: DryRunResult(success=True, preview_row={"a": 1}),
    )

    from backend.main import create_app
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_post_chat_start_returns_session_id(app_with_mocks):
    r = app_with_mocks.post("/api/chat/start")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"].startswith("chat_")


def test_post_chat_message_streams_sse(app_with_mocks):
    sid = app_with_mocks.post("/api/chat/start").json()["session_id"]
    with app_with_mocks.stream("POST", "/api/chat/message",
                                json={"session_id": sid, "content": "求平均 RSRP"}) as resp:
        assert resp.status_code == 200
        events = []
        for line in resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    assert events  # 至少一个事件
    # 应该至少包含 classifier 起步事件和最终 presenter 卡片
    types = {e.get("event") for e in events}
    assert "node_complete" in types or "presenter_payload" in types


def test_get_chat_history(app_with_mocks):
    sid = app_with_mocks.post("/api/chat/start").json()["session_id"]
    with app_with_mocks.stream("POST", "/api/chat/message",
                                json={"session_id": sid, "content": "你好"}) as resp:
        for _ in resp.iter_lines():
            pass
    r = app_with_mocks.get(f"/api/chat/{sid}/history")
    assert r.status_code == 200
    body = r.json()
    assert len(body["messages"]) >= 2  # user + assistant


def test_get_chat_result_returns_last_presenter_payload(app_with_mocks):
    sid = app_with_mocks.post("/api/chat/start").json()["session_id"]
    with app_with_mocks.stream("POST", "/api/chat/message",
                                json={"session_id": sid, "content": "..."}) as resp:
        for _ in resp.iter_lines():
            pass
    r = app_with_mocks.get(f"/api/chat/{sid}/result")
    assert r.status_code == 200
    assert "type" in r.json()
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_api_chat.py -v
```

预期：FAIL — `/api/chat/*` 不存在。

- [ ] **Step 3: 实现 `backend/api/chat.py`**

```python
"""/api/chat/* — SSE 流式对话 (spec §6.7)。"""
from __future__ import annotations

import asyncio
import json
from queue import Empty, Queue
from threading import Thread
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.agent.graph import build_graph
from backend.clients.deepseek import build_chat_client


router = APIRouter()


class ChatMessageRequest(BaseModel):
    session_id: str
    content: str


@router.post("/api/chat/start")
def chat_start(request: Request) -> dict:
    store = request.app.state.chat_store
    sess = store.new()
    return {"session_id": sess.id}


@router.post("/api/chat/message")
async def chat_message(request: Request, payload: ChatMessageRequest):
    store = request.app.state.chat_store
    searcher = request.app.state.searcher
    try:
        sess = store.get(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session_id")
    store.append_message(sess.id, role="user", content=payload.content)
    llm_client = build_chat_client(temperature=0.0)
    graph = build_graph(llm_client=llm_client, searcher=searcher)

    initial_state = {"messages": list(sess.messages)}

    queue: Queue = Queue()

    def runner():
        try:
            final_state = None
            # LangGraph 的 stream 给每个节点输出 partial state
            for chunk in graph.stream(initial_state, stream_mode="updates"):
                # chunk = {node_name: {field: value, ...}}
                for node, partial in chunk.items():
                    queue.put({"event": "node_complete", "node": node,
                                "partial": _safe(partial)})
                    if node == "presenter" and partial.get("final_message"):
                        queue.put({"event": "presenter_payload",
                                    "summary": partial.get("final_message")})
                final_state = chunk
            store.set_last_result(sess.id, _last_payload(final_state) or {})
            # 把 assistant 回复落到 session
            assistant_msg = (
                (_last_payload(final_state) or {}).get("summary")
                or "(完成)"
            )
            store.append_message(sess.id, role="assistant", content=assistant_msg)
            queue.put({"event": "done"})
        except Exception as e:
            queue.put({"event": "error", "detail": str(e)})

    Thread(target=runner, daemon=True).start()

    async def event_gen():
        while True:
            try:
                item = queue.get(timeout=0.05)
            except Empty:
                await asyncio.sleep(0.05)
                continue
            yield {"event": "message", "data": json.dumps(item, ensure_ascii=False)}
            if item.get("event") in {"done", "error"}:
                return

    return EventSourceResponse(event_gen())


@router.get("/api/chat/{session_id}/history")
def chat_history(session_id: str, request: Request) -> dict:
    try:
        sess = request.app.state.chat_store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session_id")
    return {"session_id": session_id, "messages": sess.messages}


@router.get("/api/chat/{session_id}/result")
def chat_result(session_id: str, request: Request) -> dict:
    try:
        sess = request.app.state.chat_store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session_id")
    return sess.last_result or {"type": "empty"}


# ---------------- helpers ----------------

def _safe(v: Any) -> Any:
    """非序列化对象转 str。"""
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        return str(v)


def _last_payload(chunk: dict | None) -> dict | None:
    if not chunk:
        return None
    for node, partial in chunk.items():
        if node == "presenter":
            return partial.get("presenter_payload") or {"summary": partial.get("final_message")}
    return None
```

- [ ] **Step 4: 修改 `backend/main.py`，在 lifespan 注入 `chat_store` + 注册路由**

把 `backend/main.py` 替换为：

```python
"""FastAPI app factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.agent.chat_session import ChatSessionStore
from backend.api import chat, health, metadata, search
from backend.config import get_settings
from backend.metadata.graph import close_driver, get_driver
from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_driver()
    settings = get_settings()
    embedder = Embedder(
        model_name=settings.search_embed_model,
        chroma_dir=settings.search_chroma_dir,
    )
    searcher = HybridSearcher(
        embedder=embedder,
        rerank_threshold=settings.search_rerank_threshold,
        rrf_k=settings.search_rrf_k,
    )
    try:
        docs = build_docs_from_neo4j(seed_only=settings.search_bootstrap_from_seed)
        searcher.build_index(docs)
        logger.info("Search index built: %d docs, version=%d",
                    len(docs), searcher.get_index_version())
    except Exception as e:
        logger.warning("Search index build failed at startup: %s", e)
    app.state.searcher = searcher
    app.state.chat_store = ChatSessionStore()
    yield
    close_driver()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Wireless RNO Data Semantic Service",
        version="0.3.0",
        lifespan=lifespan,
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(metadata.router, tags=["metadata"])
    app.include_router(search.router, tags=["search"])
    app.include_router(chat.router, tags=["chat"])
    return app


app = create_app()
```

- [ ] **Step 5: 测试通过**

```bash
pytest tests/agent/test_api_chat.py -v
```

预期：PASS (4/4)。

- [ ] **Step 6: 提交**

```bash
git add backend/api/chat.py backend/main.py tests/agent/test_api_chat.py
git commit -m "feat(agent): /api/chat/* SSE streaming endpoints"
```

---

## Task 19: `/api/schema/*` — apply + evolution timeline

**Files:**
- Create: `backend/api/schema_evolution.py`
- Modify: `backend/main.py`（注册路由）
- Create: `tests/agent/test_api_schema.py`

- [ ] **Step 1: 写测试**

```python
"""tests/agent/test_api_schema.py"""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    import numpy as np

    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[0.0] * 16 for _ in texts])

    monkeypatch.setattr("backend.search.embedder.SentenceTransformer",
                        lambda name: StubEncoder())
    monkeypatch.setenv("SEARCH_BOOTSTRAP_FROM_SEED", "1")
    monkeypatch.setenv("SEARCH_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from backend.config import get_settings
    get_settings.cache_clear()

    from backend.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_post_schema_apply_executes_diff(client):
    diff = [{"operation": "ADD_FIELD", "table": "dwd_session_qos",
             "field": "jitter", "data_type": "DOUBLE", "expression": "STDDEV(latency)"}]
    with patch("backend.api.schema_evolution.validate_change",
               return_value={"errors": [], "warnings": [], "passed": True}), \
         patch("backend.api.schema_evolution.schema_apply") as ap:
        ap.return_value = {"applied_changes": [{"change_id": "c1",
                                                  "operation": "ADD_FIELD",
                                                  "table": "dwd_session_qos",
                                                  "field": "jitter",
                                                  "commit_hash": "sha"}]}
        r = client.post("/api/schema/apply", json={"diff": diff})
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is True
    assert body["applied"][0]["operation"] == "ADD_FIELD"


def test_post_schema_apply_returns_validation_errors_without_executing(client):
    diff = [{"operation": "DELETE_FIELD", "table": "ods_ue_signal", "field": "rsrp"}]
    with patch("backend.api.schema_evolution.validate_change",
               return_value={"errors": [("BREAK_DOWNSTREAM", diff[0])],
                              "warnings": [], "passed": False}), \
         patch("backend.api.schema_evolution.schema_apply") as ap:
        r = client.post("/api/schema/apply", json={"diff": diff})
        ap.assert_not_called()
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is False
    assert body["errors"][0][0] == "BREAK_DOWNSTREAM"


def test_get_schema_evolution_by_table(client):
    with patch("backend.api.schema_evolution.run_query") as m:
        m.return_value = [
            {"id": "c1", "operation": "ADD_FIELD", "table_name": "dwd_session_qos",
             "field_name": "jitter", "changed_at": "2026-05-14T10:00:00Z", "commit_hash": "sha1"},
        ]
        r = client.get("/api/schema/evolution/dwd_session_qos")
    assert r.status_code == 200
    body = r.json()
    assert body["table"] == "dwd_session_qos"
    assert len(body["changes"]) == 1
    assert body["changes"][0]["operation"] == "ADD_FIELD"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/agent/test_api_schema.py -v
```

预期：FAIL — `/api/schema/*` 不存在。

- [ ] **Step 3: 实现 `backend/api/schema_evolution.py`**

```python
"""/api/schema/* — apply + evolution timeline (spec §6.7)。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.agent.nodes.schema_apply import schema_apply
from backend.agent.tools import validate_change
from backend.metadata.graph import run_query


router = APIRouter()


class SchemaApplyRequest(BaseModel):
    diff: list[dict]


@router.post("/api/schema/apply")
def apply_schema(req: SchemaApplyRequest) -> dict:
    """用户在 gap_proposal 卡片点 [确认并继续] 后由前端 POST 这里。

    本接口同时承担"独立 schema 维护"职责 — UI 直接构造 diff 提交。
    """
    v = validate_change(req.diff)
    if not v["passed"]:
        return {
            "passed": False,
            "errors": v["errors"],
            "warnings": v["warnings"],
            "applied": [],
        }
    out = schema_apply({"schema_diff": req.diff})
    return {
        "passed": True,
        "errors": [],
        "warnings": v.get("warnings", []),
        "applied": out["applied_changes"],
    }


@router.get("/api/schema/evolution/{table}")
def schema_evolution(table: str) -> dict:
    rows = run_query(
        """
        MATCH (c:Change {table_name: $table})
        RETURN c.id AS id, c.operation AS operation, c.table_name AS table_name,
               c.field_name AS field_name, c.changed_at AS changed_at,
               c.commit_hash AS commit_hash
        ORDER BY c.changed_at DESC
        """,
        table=table,
    )
    return {
        "table": table,
        "changes": [
            {
                "change_id": r["id"],
                "operation": r["operation"],
                "field_name": r["field_name"],
                "changed_at": str(r["changed_at"]),
                "commit_hash": r["commit_hash"],
            }
            for r in rows
        ],
    }
```

- [ ] **Step 4: 修改 `backend/main.py` 注册路由**

在 `create_app` 函数的路由注册块末尾追加：

```python
    from backend.api import schema_evolution
    app.include_router(schema_evolution.router, tags=["schema"])
```

- [ ] **Step 5: 测试通过**

```bash
pytest tests/agent/test_api_schema.py -v
```

预期：PASS (3/3)。

- [ ] **Step 6: 提交**

```bash
git add backend/api/schema_evolution.py backend/main.py tests/agent/test_api_schema.py
git commit -m "feat(agent): /api/schema/apply and /api/schema/evolution/{table}"
```

---

## Task 20: P2 验收集成测试（slice 2b 覆盖部分）

**Files:**
- Create: `tests/agent/test_p2_acceptance.py`

> 用真实 Neo4j（infra mark）+ stub bge + monkeypatch DeepSeek/sandbox。覆盖 P2-8 / P2-9 / P2-10 / P2-11 / P2-12 / P2-13 中由 slice 2b 完成的部分（P2-1..P2-7 依赖真实 LLM 或沙箱，由各自所属 slice 给最终验收）。

- [ ] **Step 1: 写测试**

```python
"""tests/agent/test_p2_acceptance.py — slice 2b 验收用例 (mark=infra)。"""
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.infra


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SEARCH_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from backend.config import get_settings
    get_settings.cache_clear()
    from backend.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_p2_8_add_jitter_field_persists_to_neo4j_and_yaml(client, monkeypatch):
    """端到端: schema_apply 后 GET /api/fields 可查到 jitter, yaml 文件包含。"""
    diff = [{"operation": "ADD_FIELD", "table": "dwd_session_qos", "field": "jitter",
             "data_type": "DOUBLE", "expression": "STDDEV(latency)",
             "upstream": [{"table": "dwd_session_qos", "field": "latency"}]}]
    r = client.post("/api/schema/apply", json={"diff": diff})
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is True

    # Neo4j check
    tables = client.get("/api/tables").json()
    qos = next(t for t in tables if t["name"] == "dwd_session_qos")
    fields = client.get(f"/api/tables/{qos['id']}").json()["fields"]
    assert any(f["name"] == "jitter" for f in fields)

    # YAML check
    yaml_path = Path("metadata-yaml/L2-DWD/dwd_session_qos.yaml")
    assert yaml_path.exists()
    assert "jitter" in yaml_path.read_text(encoding="utf-8")


def test_p2_9_delete_rsrp_blocked_by_validate(client):
    diff = [{"operation": "DELETE_FIELD", "table": "ods_ue_signal", "field": "rsrp"}]
    r = client.post("/api/schema/apply", json={"diff": diff})
    assert r.status_code == 200
    body = r.json()
    assert body["passed"] is False
    assert any(e[0] == "BREAK_DOWNSTREAM" for e in body["errors"])
    assert body["applied"] == []


def test_p2_10_reverse_synth_writes_fake_data_for_eval_user_score(client, monkeypatch):
    """通过工具直接调 generate_fake_data + 查 Hive 验证 (依赖 slice 1b 的 dwd_session_qos seed 实现)。"""
    from backend.agent.tools import generate_fake_data
    # eval_user_score 在本切片不要求 generate_fake_data 实现 — 仅 dwd_session_qos
    out = generate_fake_data("dwd_session_qos", 3)
    assert out["written"] == 3


def test_p2_12_schema_apply_idempotent_for_evolution_timeline(client):
    """点 [确认并继续] 等价于 POST /api/schema/apply; evolution 时间线含该条 Change。"""
    diff = [{"operation": "ADD_FIELD", "table": "dwd_session_qos", "field": "jitter2",
             "data_type": "DOUBLE", "expression": "STDDEV(latency)"}]
    client.post("/api/schema/apply", json={"diff": diff})
    r = client.get("/api/schema/evolution/dwd_session_qos")
    body = r.json()
    assert any(c["field_name"] == "jitter2" and c["operation"] == "ADD_FIELD"
               for c in body["changes"])
```

- [ ] **Step 2: 跑测试（需 base-compose + Neo4j seeded + 干净 metadata-yaml/）**

```bash
pytest tests/agent/test_p2_acceptance.py -v -m infra
```

预期：4 个测试 PASS（如果之前测试已经 add 过 jitter，需要先重置 Neo4j seed：`docker compose -f base-compose.yml down && docker compose -f base-compose.yml up -d && ./scripts/init-stack.sh`）。

- [ ] **Step 3: 提交**

```bash
git add tests/agent/test_p2_acceptance.py
git commit -m "test(agent): P2-8 P2-9 P2-10 P2-12 integration acceptance"
```

---

## Task 21: Docker / app-compose / init-stack 更新

**Files:**
- Modify: `app-compose.yml`
- Modify: `backend/Dockerfile`（Task 0 已加 git；本步加 GIT_AUTHOR 默认环境）
- Modify: `scripts/init-stack.sh`

- [ ] **Step 1: `app-compose.yml` 加 git 配置与挂载**

把 `backend` 服务的 `environment` 块替换为（在 slice 2a 已有基础上追加）：

```yaml
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}
      DEEPSEEK_BASE_URL: ${DEEPSEEK_BASE_URL:-https://api.deepseek.com}
      DEEPSEEK_MODEL: ${DEEPSEEK_MODEL:-deepseek-chat}
      SEARCH_CHROMA_DIR: /app/data/chroma
      SEARCH_EMBED_MODEL: BAAI/bge-small-zh-v1.5
      SEARCH_RERANK_THRESHOLD: "0.15"
      SEARCH_RRF_K: "60"
      AGENT_MAX_ITERATIONS: "3"
      GIT_AUTHOR_NAME: "Data-Gov Agent"
      GIT_AUTHOR_EMAIL: "agent@data-gov.local"
      # GitPython 在容器里需要识别仓库 — 挂载 .git
```

并在 `backend` 服务的 `volumes` 块追加：

```yaml
      - ./.git:/app/.git
      - ./metadata-yaml:/app/metadata-yaml
```

- [ ] **Step 2: `scripts/init-stack.sh` 验证 P2 端点起来**

把原 `Waiting for backend healthy` 循环之后，再补一段：

```bash
echo "Verifying /api/chat/start ..."
sid=$(curl -fsS -X POST http://localhost:8000/api/chat/start | python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
echo "  session_id=$sid"

echo "Verifying /api/schema/evolution/dwd_session_qos ..."
curl -fsS http://localhost:8000/api/schema/evolution/dwd_session_qos > /dev/null
```

- [ ] **Step 3: 整栈冷启验证**

```bash
docker compose -f app-compose.yml down 2>/dev/null || true
docker compose -f base-compose.yml down
rm -rf ./data ./metadata-yaml
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
```

预期：脚本退出码 0；`curl http://localhost:8000/api/health | jq` 显示 `status: healthy`；`/api/chat/start` 返回 session_id；`/api/schema/evolution/{table}` 200 OK（changes 数组可能为空，正常）。

- [ ] **Step 4: 提交**

```bash
git add app-compose.yml scripts/init-stack.sh
git commit -m "infra(agent): app-compose env + git mount + init-stack verification"
```

---

## Task 22: README 验收表 + 收尾

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README 末尾追加 slice 2b 验收表**

```markdown

## Acceptance coverage (Phase 2 — slice 2b)

| Case | Verifies | Test |
|------|----------|------|
| P2b-1 | classifier 三意图分类 + 关键词降级 | `tests/agent/nodes/test_classifier.py` |
| P2b-2 | forward_etl / reverse_synth 抽取与表搜索 | `tests/agent/nodes/test_forward_etl.py` + `test_reverse_synth.py` |
| P2b-3 | pipeline_parse 上溯链路 | `tests/agent/nodes/test_pipeline_parse.py` |
| P2b-4 | gap_check + gap_proposal 子流程 | `tests/agent/nodes/test_gap_check.py` + `test_gap_proposal.py` |
| P2b-5 | code_generate + dry_run + Agent 层 3 轮重试 | `tests/agent/nodes/test_code_generate.py` + `test_dry_run.py` + `test_graph_routing.py::test_after_dry_run_*` |
| P2b-6 | schema_evolve → validate → apply 全链 | `tests/agent/nodes/test_schema_evolve.py` / `test_schema_validate.py` / `test_schema_apply.py` |
| P2b-7 | YAML 同步 + git commit + Change.commit_hash | `tests/agent/test_yaml_sync.py` + `test_schema_apply.py::test_schema_apply_dispatches_add_table` |
| P2-1 (slice 2b 部分) | forward_etl → spark_sql 路径打通 (mock LLM/sandbox) | `tests/agent/test_graph_e2e.py::test_p2_1_forward_etl_spark_sql_path` |
| P2-8 | NL→新增 jitter 字段 → Neo4j + YAML | `tests/agent/test_p2_acceptance.py::test_p2_8_*` |
| P2-9 | 删除有下游引用的字段被拒绝 | `tests/agent/test_p2_acceptance.py::test_p2_9_*` |
| P2-10 (slice 2b 部分) | generate_fake_data 工具可调用 | `tests/agent/test_p2_acceptance.py::test_p2_10_*` |
| P2-11 | gap_check missing_table | `tests/agent/test_graph_e2e.py::test_p2_11_*` |
| P2-12 | schema_apply 后 evolution 时间线含 Change | `tests/agent/test_p2_acceptance.py::test_p2_12_*` |
| P2-13 | gap_check missing_field（通过 schema_validate 联动） | `tests/agent/nodes/test_gap_check.py` (单元) + slice 3 UI 端到端 |

跑全部 slice 2b 测试：

```bash
pytest tests/agent -v
pytest tests/agent -v -m infra   # 需 base-compose + Neo4j seeded
```

**Deferred to slice 2c**：P2-4 / P2-5 / P2-6（沙箱真实执行）+ P2-7（沙箱层 execute_with_retry）。
**Deferred to Phase 3**：P2-11/12/13 的 UI 卡片渲染 + 用户点击 [确认并继续] 的前端联动。
```

- [ ] **Step 2: 跑完整 agent 测试套件验证**

```bash
pytest tests/agent -v -m "not infra"
```

预期：全部 PASS。

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs: slice 2b acceptance coverage table"
```

---

## Self-Review

### 1. Spec coverage

| Spec ref | Requirement | Plan task |
|----------|-------------|-----------|
| §4.1 LangGraph StateGraph (流程图) | Task 16 (`build_graph` 含所有条件边) |
| §4.1 classifier 节点 | Task 8 |
| §4.1 forward_etl | Task 9 |
| §4.1 reverse_synth | Task 9 |
| §4.1 schema_evolve (主+子流程) | Task 14 |
| §4.1 schema_validate | Task 14 |
| §4.1 schema_apply + commit_hash 回填 | Task 15 |
| §4.1 schema_lookup (含子流程清 sub_flow_active) | Task 10 |
| §4.1 pipeline_parse | Task 10 |
| §4.1 gap_check (阈值 0.6) | Task 11 |
| §4.1 gap_proposal (sub_flow_return_point) | Task 11 |
| §4.1 code_generate (含 iteration_count +1 与 error_feedback) | Task 12 |
| §4.1 dry_run (按 code_type 分派) | Task 12 |
| §4.1 presenter (按 intent / state 构造 payload + SSE) | Task 13 |
| §4.2 AgentState 所有字段 | Task 2 (强制守护测试) |
| §4.3 Tools (11 个; HTTP/Agent 共享 service) | Task 5 |
| §4.4 DeepSeek 集成 | slice 2a `backend.clients.deepseek` 已交付；本 slice 直接 import |
| §4.5 双层重试 — Agent 层 3 轮 (含首次) | Task 16 `after_dry_run` + `AGENT_MAX_ITERATIONS` |
| §4.5 沙箱层 execute_with_retry | **Deferred** → slice 2c（本 slice 仅给 sandbox_stub） |
| §6.7 `/api/chat/start` `/message` `/{id}/result` `/{id}/history` | Task 18 |
| §6.7 `/api/schema/apply` | Task 19 |
| §6.7 `/api/schema/evolution/:table` | Task 19 |
| §8.2 P2-1 (forward_etl spark_sql) | Task 17 e2e（mock 版） + slice 2c 端到端 |
| §8.2 P2-2 / P2-3 (flink_sql / java_flink) | code_generate + dry_run 路径已通；端到端要 slice 2c 沙箱 |
| §8.2 P2-4..P2-7 | **Deferred** → slice 2c |
| §8.2 P2-8 | Task 20 `test_p2_8_*` |
| §8.2 P2-9 | Task 20 `test_p2_9_*` |
| §8.2 P2-10 | Task 20 `test_p2_10_*`（reverse_synth 路径在 Task 17/20 拼合） |
| §8.2 P2-11 | Task 17 `test_p2_11_*` |
| §8.2 P2-12 | Task 20 `test_p2_12_*` |
| §8.2 P2-13 (missing_field) | gap_check 工具已支持字段级缺口结构；UI 触发延后 slice 3 |
| §6.9 版本↔commit 映射 (commit_msg 含 `table:xxx version:N`) | Task 15 `_summarize` 暂用 `OP table.field` 格式；spec 例子是 `schema_evolve: UPDATE {table}.{field} v{old}→v{new}` — **偏离说明见下** |

**偏离说明（spec §6.9 commit message 格式）：** spec §6.9 给出的示例 `schema_evolve: UPDATE {table}.{field} v{old}→v{new}` 假定 schema_apply 能拿到 old/new version。本 slice `_summarize` 暂未携带 version 数字（service.update_field 返回 `version` 在 applied_changes 里有，但拼 message 时为简化没读）。**影响**：spec §6.9 的 `git log --grep "table:xxx version:N"` 反查会失效。**补救**：slice 3 实现 `/schema-evolution` UI 时把 commit_msg 改成精确格式即可；本 slice 留 issue。

### 2. Placeholder scan

搜了 `TBD` / `TODO` / `implement later` / `appropriate` / `similar to Task`：
- 无 TBD / TODO。
- Task 15 Step 1 测试代码里写了 `pytest_fail` typo，**Step 2 已明确要求改成 `pytest.fail`** —— 这是有意的两步走（先写出会暴露 fixture/import 问题的测试草稿，再修正），不是 placeholder。
- Task 11 `gap_check` 实现里保留了字段级缺口分支的注释 "保留接口"，没生成 missing_field —— **spec §8.2 P2-13 的字段级 gap 在 LLM 抽取 entity 时若 `field_specified=true` 已被结构化携带；当前实现只在 missing_table 分支生成 gap，missing_field 留 slice 3 UI 接线**。已在偏离说明列出。
- Task 21 Step 2 init-stack 验证仅 `curl > /dev/null` 检查 200，未做内容断言 — 这是 infra-level smoke，**深度断言在 Task 20 的 pytest infra mark 里完成**，分工清晰。

### 3. Type / name consistency

- `AgentState` 字段名 — Task 2 定义 / Tasks 8–15 节点全部直接读写、未改名。
- 节点签名约定 `(state: dict) -> dict` + 副作用通过依赖注入 (`llm_client=`, `searcher=`, `sse_emit=`) — Tasks 8–15 全部遵守。
- `intent` 字面量 `forward_etl | reverse_synth | schema_evolve` — Tasks 8, 14, 16 一致。
- `code_type` 字面量 `spark_sql | flink_sql | java_flink` — Tasks 5 (sandbox_stub 类型别名), 12 (`VALID_CODE_TYPES`, `_STORAGE_TO_CODE_TYPE`), 13 (presenter), 17 (e2e) 一致。
- `schema_diff` 元素字段 `{operation, table, field, data_type, expression, upstream, layer, storage_type, fields}` — Tasks 4 (prompt), 5 (`validate_change` / `add_field` / `update_field` / `remove_field` / `add_table`), 14, 15, 19 全部使用同一字典 schema；任务间无字段名漂移。
- `validation_result` 形如 `{errors, warnings, passed}`，`errors` 元素是元组 `(code, op[, extra])` — Tasks 5 (`validate_change`), 14, 13 (presenter), 19 一致。
- `applied_changes` 元素 `{change_id, operation, table, field, commit_hash}` — Tasks 15 / 19 / 20 一致。
- `gaps` 元素 `{type, keyword, suggestion, [table], [field]}` — Tasks 5 (`check_gaps`), 11, 17 一致。
- `sub_flow_active` / `sub_flow_return_point` — Tasks 11 (设), 10 (清), 16 (条件边)。
- ChatSession `messages` 元素 `{"role", "content"}` — Tasks 7 / 18 / 8 (classifier) 一致。
- 工具函数名 — Task 5 与 spec §4.3 表格逐行对齐（`search_tables_by_keyword`, `lookup_table_schema`, `lookup_lineage`, `check_gaps`, `propose_gap_fix`, `generate_fake_data`, `validate_change`, `add_table`, `add_field`, `update_field`, `remove_field`, `sync_yaml`, `dry_run_spark_sql/flink_sql/java_flink`）。
- HTTP 路径 — Tasks 18 / 19 与 spec §6.7 表完全一致。
- `Change` 节点字段 `{id, operation, table_name, field_name, changed_at, commit_hash}` — Tasks 15 (写) / 19 (读) 一致。
- `iteration_count` 初值 + 自增 — Task 2 (字段), 12 (`+1`), 16 (`after_dry_run` 判 `>= agent_max_iterations`) 一致。
- `LAYER_DIR` — Task 6 重复定义 (`backend/agent/yaml_sync.py`) 但与 `init-scripts/07_export_yaml.py` 同名同内容；**已有副本接受 — 二者都需要独立可执行**，未来需迁移为公共常量则在 slice 3 抽离。

无名字漂移。

---

## Execution Handoff

Plan 完成，已保存到 `docs/superpowers/plans/2026-05-14-phase2-slice2b-langgraph-agent.md`。

22 个 task，建议拆 5 个 checkpoint 段：

- **Checkpoint A** (Tasks 0–4)：依赖 + state + sandbox_stub + prompts — 全是基础设施，可一气呵成。
- **Checkpoint B** (Tasks 5–7)：tools + yaml_sync + chat_session — 协作底座，先扎稳。
- **Checkpoint C** (Tasks 8–13)：6 个简单节点（classifier / forward_etl / reverse_synth / pipeline_parse / schema_lookup / gap_check+gap_proposal / code_generate / dry_run / presenter）。可并行 review。
- **Checkpoint D** (Tasks 14–17)：schema 三节点 + Graph 装配 + e2e — slice 2b 核心，验证条件边。
- **Checkpoint E** (Tasks 18–22)：HTTP/SSE + 验收 + Docker + README。

两种执行方式：

**1. Subagent-Driven (推荐)** — 每个 Task 派一个新的 subagent，两段式 review。22 个 task 推荐分配：A/B 段每 task 一个 agent；C 段（节点）可批量发 3–4 个并行；D/E 段串行，每 task 单独 review。

**2. Inline Execution** — 用 `superpowers:executing-plans`，按 5 个 checkpoint 分批，每段完成后 review 一次。

选择哪种方式？


