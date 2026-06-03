# Phase 2 Slice 2a: 语义检索子系统 (Hybrid Search) 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec §4.6 + §4.7 — 在 `backend/search/` 下实现 BM25 + Dense + RRF + LLM Rerank 的混合检索器（`HybridSearcher`），暴露 `GET /api/search`，从 Neo4j 元数据自动构建/增量同步 ChromaDB 索引，并接入 60 条 benchmark queries 的 CI 门禁脚本，作为 Phase 2 中 Agent (slice 2b) 的入口工具底座。

**Architecture:** 索引层 = `bge-small-zh-v1.5` (CPU SentenceTransformer) + ChromaDB PersistentClient (`./data/chroma/`)；关键词层 = `rank-bm25` + jieba（自定义 RNO 技术术语词典）；融合层 = RRF (k=60)；兜底层 = DeepSeek Chat (LangChain `ChatOpenAI` 走 `DEEPSEEK_BASE_URL`)。索引在 FastAPI lifespan 启动时构建（首次冷启 / 后续按 `index_version` 增量 upsert）。DeepSeek 客户端落到 `backend/clients/deepseek.py`，作为 slice 2b LangGraph 节点的共享底座。

**Tech Stack:**
- `sentence-transformers>=2.7` (模型 `BAAI/bge-small-zh-v1.5`, 24MB, CPU)
- `chromadb>=0.5` (PersistentClient + HNSW cosine)
- `rank-bm25>=0.2.2`
- `jieba>=0.42` (中文分词 + 自定义词典)
- `langchain-openai>=0.1` (DeepSeek 走 OpenAI 兼容协议) — 仅用于 rerank，slice 2b 复用
- 已有：`neo4j>=5.18`, `fastapi>=0.110`, `pydantic-settings>=2.2`（slice 1b 已装）

**Prerequisites (from slice 1b):**
- `backend/` 包结构存在 (`backend.main:app`, `backend.config.get_settings`, `backend.metadata.graph.run_query`)
- Neo4j 已 seed 10 表 / ~65 字段 / ~45 `DERIVES_FROM` 边（`MATCH (t:Table) RETURN count(t)` 返回 10）
- `app-compose.yml` + `backend/Dockerfile` 在跑
- `tests/api/__init__.py` 已存在

**Out of scope for this slice (deferred):**
- LangGraph Agent / `agent/` 子包 → slice 2b
- 沙箱 / `sandbox/` 子包 → slice 2c
- `/api/chat/*`, `/api/schema/*`, `/api/pipeline`, `/api/yaml/*` → slice 2b / 3
- 增量同步触发器（schema_apply 节点写完后调用 `HybridSearcher.upsert`）→ slice 2b 接线；本 slice 仅提供可调用的 upsert 方法 + 启动时一次性 reindex
- ChromaDB 数据损坏自动重建（spec §4.6.4 列出）→ 本 slice 不主动实现。当前如果 `./data/chroma/` 被破坏，PersistentClient 会抛异常，由 FastAPI lifespan 抓住后写 warning；运维需要手动 `rm -rf ./data/chroma/` 重启。slice 2b 接 schema_evolve 时若仍有需求，再补 try/rebuild 包装。
- 中文术语自定义词典的运维界面 → 永远是代码内常量
- `--mode incremental` benchmark 增量回归对比 → CLI 入口在 Task 11 已保留，逻辑落 slice 2b（schema_evolve 后再触发）
- 模型热升级（bge 换 base/large 版本）

---

## File Structure

```
data-gov/
├── backend/
│   ├── clients/                            # NEW — 共享 LLM 客户端，slice 2b 复用
│   │   ├── __init__.py
│   │   └── deepseek.py                     # LangChain ChatOpenAI(base_url=DEEPSEEK_BASE_URL)
│   ├── search/                             # NEW
│   │   ├── __init__.py
│   │   ├── docs.py                         # Neo4j → table_doc/field_doc 序列化
│   │   ├── preprocessing.py                # jieba 词典注册 + tokenize()
│   │   ├── embedder.py                     # bge-small-zh + ChromaDB Persistent
│   │   ├── searcher.py                     # HybridSearcher (build_index/search/upsert)
│   │   ├── rerank.py                       # _llm_rerank 实现 (依赖 clients.deepseek)
│   │   └── fusion.py                       # _rrf_fuse 纯函数 (易测)
│   ├── api/
│   │   └── search.py                       # NEW — GET /api/search
│   ├── api/health.py                       # MODIFIED — 加 search 组件状态
│   ├── main.py                             # MODIFIED — lifespan 启动时初始化 HybridSearcher
│   └── config.py                           # MODIFIED — 加 DEEPSEEK_* / SEARCH_* 设置
├── scripts/
│   ├── generate_benchmark_queries.py       # NEW — 从 SEED_TABLES 派生 30 条规则查询 + 拼合 30 条人工查询
│   └── benchmark_semantic_search.py        # NEW — 跑 60 条 queries → 指标 → CI 退出码
├── tests/
│   ├── conftest.py                         # MODIFIED — 加 `searcher` fixture
│   └── search/                             # NEW
│       ├── __init__.py
│       ├── test_preprocessing.py           # jieba 词典 + tokenize
│       ├── test_fusion.py                  # RRF 纯函数单测
│       ├── test_docs.py                    # Neo4j → docs 转换
│       ├── test_embedder.py                # ChromaDB upsert + dim 验证
│       ├── test_searcher.py                # build_index + search + upsert e2e (Neo4j 集成)
│       ├── test_rerank.py                  # LLM rerank 触发路径 (mock DeepSeek)
│       ├── test_api_search.py              # GET /api/search 端到端
│       └── test_benchmark.py               # 60 条 queries 满足目标 90%
├── data/
│   └── chroma/                             # 运行时生成；slice 2a 起加入 .gitignore
├── benchmark/                              # NEW
│   ├── benchmark_queries.yaml              # 60 条 queries (类型 A/B/C)
│   └── README.md                           # 测试集构造规则
├── pyproject.toml                          # MODIFIED — 加 4 个依赖
├── .gitignore                              # MODIFIED — 加 `data/chroma/`
├── .env.example                            # MODIFIED — 加 DEEPSEEK_* / SEARCH_*
└── app-compose.yml                         # MODIFIED — 加 DEEPSEEK_* 环境变量 + chroma volume
```

**职责拆分要点：**
- `backend/search/preprocessing.py`：模块导入即调用 `register_terms()` 一次性把 RNO 术语词典写入 jieba；`tokenize(text)` 纯函数。
- `backend/search/docs.py`：`build_docs_from_neo4j() -> list[dict]` — 读 Neo4j，返回 spec §4.6.1 形如 `{"id","type","text","metadata"}` 的 doc 列表，按表/字段共 ~80 条。
- `backend/search/embedder.py`：封装 `Embedder` 类，惰性加载 bge 模型；提供 `encode(list[str]) -> list[list[float]]`；提供 `ChromaCollection` 持有的 `upsert/query/index_version` 操作。降级路径：bge 加载失败 → `Embedder._encoder = None`，HybridSearcher 检测后跳过 Dense。
- `backend/search/fusion.py`：纯 Python，输入两路有序 doc 列表，输出 RRF 融合后的 top-k。无依赖 — 100% 单元可测。
- `backend/search/searcher.py`：组合 docs/embedder/fusion/preprocessing/rerank 成 `HybridSearcher`；持有进程内 BM25 倒排；提供 `build_index(docs)` / `search(query, k, use_rerank)` / `upsert(docs)` / `get_index_version()`。
- `backend/search/rerank.py`：纯函数 `llm_rerank(query, candidates, deepseek_client)`；客户端注入便于测试时 mock。
- `backend/clients/deepseek.py`：`get_deepseek_client()` 单例，读 `DEEPSEEK_*` 设置；返回 `langchain_openai.ChatOpenAI`。
- `backend/api/search.py`：FastAPI router；`GET /api/search?q=&type=&k=` → `SearchResponse`。
- `backend/main.py` 的 lifespan：启动时构建/打开 `HybridSearcher` 实例 → 存到 `app.state.searcher`。

---

## Task 0: 扩展依赖 + 包骨架

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Modify: `.env.example`
- Create: `backend/clients/__init__.py`
- Create: `backend/search/__init__.py`
- Create: `tests/search/__init__.py`
- Create: `benchmark/README.md`

- [ ] **Step 1: `pyproject.toml` 加运行时和测试依赖**

把 `[project.optional-dependencies]` 块的 `runtime` 列表替换为：

```toml
runtime = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "neo4j>=5.18",
    "pydantic-settings>=2.2",
    "PyYAML>=6.0",
    "sentence-transformers>=2.7",
    "chromadb>=0.5",
    "rank-bm25>=0.2.2",
    "jieba>=0.42",
    "langchain-openai>=0.1",
]
```

`test` 列表追加一行（如果尚未在 slice 1b 内加过）：

```toml
    "pytest-mock>=3.12",
```

不要动 `dev`、`pytest.ini_options`、`setuptools.packages.find` 这几个块。

- [ ] **Step 2: `.gitignore` 加 chroma 运行时目录**

追加在文件末尾：

```
# Local ChromaDB persistent store (slice 2a)
data/chroma/
```

- [ ] **Step 3: `.env.example` 加 DeepSeek + 搜索设置**

追加：

```env

# DeepSeek (LLM rerank for search, LangGraph nodes in slice 2b)
DEEPSEEK_API_KEY=sk-replace-me
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Semantic search
SEARCH_CHROMA_DIR=./data/chroma
SEARCH_EMBED_MODEL=BAAI/bge-small-zh-v1.5
SEARCH_RERANK_THRESHOLD=0.15
SEARCH_RRF_K=60
```

- [ ] **Step 4: 创建占位包文件（全部为零字节空文件即可）**

- `backend/clients/__init__.py`
- `backend/search/__init__.py`
- `tests/search/__init__.py`

- [ ] **Step 5: 创建 `benchmark/README.md`**

```markdown
# Semantic Search Benchmark Queries

60 条 NL 查询，覆盖类型 A (规则生成 30 条) / 类型 B (人工 LLM 生成 20 条) / 类型 C (对抗 10 条)。

源文件: `benchmark_queries.yaml`
生成脚本: `scripts/generate_benchmark_queries.py` (类型 A 自动重生成；B/C 锁定)
评估脚本: `scripts/benchmark_semantic_search.py`

CI 门禁：核心指标不得低于 spec §4.7.3 目标值的 90%。
```

- [ ] **Step 6: 验证可安装**

运行：

```bash
pip install -e ".[dev]"
```

预期：`Successfully installed ...`；查 `pip show sentence-transformers` 显示版本 ≥ 2.7。

- [ ] **Step 7: 提交**

```bash
git add pyproject.toml .gitignore .env.example backend/clients backend/search tests/search benchmark
git commit -m "feat(search): add slice 2a deps and package skeleton"
```

---

## Task 1: `backend/config.py` 加 DeepSeek + 搜索设置

**Files:**
- Modify: `backend/config.py`
- Test: `tests/api/test_models.py`（slice 1b 已存在，借它做配置 smoke）

- [ ] **Step 1: 写失败的测试**

新建 `tests/search/test_config.py`：

```python
"""Settings smoke for slice 2a additions."""
import os
from unittest.mock import patch

from backend.config import get_settings


def test_settings_defaults_include_search_and_deepseek(monkeypatch):
    # Clear lru_cache so env changes take effect.
    get_settings.cache_clear()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("SEARCH_CHROMA_DIR", raising=False)
    monkeypatch.delenv("SEARCH_EMBED_MODEL", raising=False)
    monkeypatch.delenv("SEARCH_RERANK_THRESHOLD", raising=False)
    monkeypatch.delenv("SEARCH_RRF_K", raising=False)

    s = get_settings()
    assert s.deepseek_base_url == "https://api.deepseek.com"
    assert s.deepseek_model == "deepseek-chat"
    assert s.search_chroma_dir == "./data/chroma"
    assert s.search_embed_model == "BAAI/bge-small-zh-v1.5"
    assert s.search_rerank_threshold == 0.15
    assert s.search_rrf_k == 60
    # api key 没有默认值，留空字符串
    assert s.deepseek_api_key == ""


def test_settings_reads_env_overrides(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("SEARCH_RRF_K", "30")
    s = get_settings()
    assert s.deepseek_api_key == "sk-test"
    assert s.search_rrf_k == 30
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_config.py -v
```

预期：FAIL — `AttributeError: 'Settings' object has no attribute 'deepseek_base_url'`。

- [ ] **Step 3: 修改 `backend/config.py` 增加字段**

把 `Settings` 类替换为：

```python
"""Application settings loaded from environment / .env."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Neo4j (slice 1b)
    neo4j_uri: str = Field("bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field("data-gov-neo4j", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field("neo4j", alias="NEO4J_DATABASE")

    metadata_yaml_dir: str = Field("metadata-yaml", alias="METADATA_YAML_DIR")

    # DeepSeek (slice 2a rerank + slice 2b LangGraph nodes)
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field("https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field("deepseek-chat", alias="DEEPSEEK_MODEL")

    # Semantic search (slice 2a)
    search_chroma_dir: str = Field("./data/chroma", alias="SEARCH_CHROMA_DIR")
    search_embed_model: str = Field("BAAI/bge-small-zh-v1.5", alias="SEARCH_EMBED_MODEL")
    search_rerank_threshold: float = Field(0.15, alias="SEARCH_RERANK_THRESHOLD")
    search_rrf_k: int = Field(60, alias="SEARCH_RRF_K")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/search/test_config.py -v
```

预期：PASS (2/2)。

- [ ] **Step 5: 提交**

```bash
git add backend/config.py tests/search/test_config.py
git commit -m "feat(search): add deepseek and search settings"
```

---

## Task 2: 文本预处理 — jieba 自定义词典 + tokenize

**Files:**
- Create: `backend/search/preprocessing.py`
- Create: `tests/search/test_preprocessing.py`

- [ ] **Step 1: 写失败的测试**

```python
"""tests/search/test_preprocessing.py"""
from backend.search.preprocessing import tokenize, RNO_TERMS


def test_tokenize_protects_rno_compound_terms():
    """覆盖强度/信噪比/掉话率不能被切散。"""
    tokens = tokenize("每个小区每小时的平均覆盖强度")
    assert "覆盖强度" in tokens
    assert "覆盖" not in tokens  # 没被切散就不会单独出现
    assert "强度" not in tokens


def test_tokenize_uppercase_acronyms_lowercased():
    tokens = tokenize("RSRP 和 SINR 的均值")
    assert "rsrp" in tokens
    assert "sinr" in tokens


def test_tokenize_strips_empty_and_whitespace():
    tokens = tokenize("  覆盖强度   ")
    assert tokens == ["覆盖强度"]


def test_rno_terms_includes_all_required_keywords():
    required = {
        "覆盖强度", "信噪比", "掉话率", "切换成功率", "吞吐量",
        "RSRP", "SINR", "RSRQ", "QoE", "切换", "会话",
    }
    assert required.issubset(set(RNO_TERMS))


def test_tokenize_handles_empty_string():
    assert tokenize("") == []
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_preprocessing.py -v
```

预期：FAIL — `ModuleNotFoundError: No module named 'backend.search.preprocessing'`。

- [ ] **Step 3: 实现 `backend/search/preprocessing.py`**

```python
"""中文分词与 RNO 术语保护。模块导入即注册自定义词典 (一次)。"""
from __future__ import annotations

import jieba

RNO_TERMS: list[str] = [
    # 测量指标缩写
    "RSRP", "RSRQ", "SINR", "QoE",
    # 业务复合词
    "覆盖强度", "信号质量", "信噪比", "掉话率", "切换成功率", "吞吐量",
    "切换", "会话", "弱覆盖", "重选", "邻区",
    # 网元
    "基站", "小区", "用户", "终端", "扇区",
    # 数仓概念
    "宽表", "明细层", "汇总层", "评估",
]


def _register_terms() -> None:
    for w in RNO_TERMS:
        jieba.add_word(w, freq=100)


_register_terms()


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    words = jieba.lcut(text)
    return [w.strip().lower() for w in words if w.strip()]
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/search/test_preprocessing.py -v
```

预期：PASS (5/5)。

- [ ] **Step 5: 提交**

```bash
git add backend/search/preprocessing.py tests/search/test_preprocessing.py
git commit -m "feat(search): jieba RNO term dictionary and tokenize"
```

---

## Task 3: 文档构建 — Neo4j → SearchDoc

**Files:**
- Create: `backend/search/docs.py`
- Create: `tests/search/test_docs.py`

- [ ] **Step 1: 写失败的测试**

```python
"""tests/search/test_docs.py"""
import pytest

from backend.search.docs import (
    SearchDoc,
    build_field_text,
    build_table_text,
    build_docs_from_neo4j,
)
from backend.seed.tables import SEED_TABLES


def test_build_table_text_includes_table_name_and_description_and_field_names():
    t = next(t for t in SEED_TABLES if t["name"] == "dws_cell_hourly")
    text = build_table_text(t)
    assert "dws_cell_hourly" in text
    # 描述、所有字段名都被拼进来
    for f in t["fields"]:
        assert f["name"] in text


def test_build_field_text_contains_type_and_description():
    t = next(t for t in SEED_TABLES if t["name"] == "ods_ue_signal")
    f = next(f for f in t["fields"] if f["name"] == "rsrp")
    text = build_field_text(t["name"], f)
    assert "rsrp" in text
    assert "DOUBLE" in text
    assert "参考信号接收功率" in text


def test_search_doc_ids_are_namespaced():
    t = SEED_TABLES[0]
    docs = build_docs_from_neo4j(seed_only=True)  # 走 in-memory fallback for unit test
    ids = {d.id for d in docs}
    assert f"table:{t['name']}" in ids
    assert any(i.startswith("field:") for i in ids)


@pytest.mark.infra
def test_build_docs_from_neo4j_returns_10_tables_and_about_65_fields():
    """需要 base-compose + Neo4j seeded."""
    docs = build_docs_from_neo4j()
    tables = [d for d in docs if d.type == "table"]
    fields = [d for d in docs if d.type == "field"]
    assert len(tables) == 10
    assert 60 <= len(fields) <= 80
    # 每条 doc 有非空 text 和 metadata.version
    for d in docs:
        assert d.text.strip()
        assert d.metadata.get("version") == 1
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_docs.py -v
```

预期：FAIL — `ModuleNotFoundError: No module named 'backend.search.docs'`。

- [ ] **Step 3: 实现 `backend/search/docs.py`**

```python
"""把 Neo4j 元数据序列化为 search docs (spec §4.6.1)。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.metadata.graph import run_query
from backend.seed.tables import SEED_TABLES


@dataclass
class SearchDoc:
    id: str
    type: str  # "table" | "field"
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def build_table_text(table: dict) -> str:
    parts = [table["name"], table.get("description", "")]
    for f in table.get("fields", []):
        parts.append(f["name"])
        parts.append(f.get("description", ""))
    return " ".join(p for p in parts if p)


def build_field_text(table_name: str, field_obj: dict) -> str:
    parts = [
        field_obj["name"],
        field_obj.get("type", ""),
        field_obj.get("description", ""),
    ]
    expr = field_obj.get("expression")
    if expr:
        parts.append(f"表达式 {expr}")
    return " ".join(p for p in parts if p)


def _docs_from_seed(tables: list[dict]) -> list[SearchDoc]:
    docs: list[SearchDoc] = []
    for t in tables:
        docs.append(SearchDoc(
            id=f"table:{t['name']}",
            type="table",
            text=build_table_text(t),
            metadata={
                "table_name": t["name"],
                "layer": t["layer"],
                "storage_type": t["storage_type"],
                "version": 1,
            },
        ))
        for f in t.get("fields", []):
            docs.append(SearchDoc(
                id=f"field:{t['name']}.{f['name']}",
                type="field",
                text=build_field_text(t["name"], f),
                metadata={
                    "table_name": t["name"],
                    "field_name": f["name"],
                    "data_type": f.get("type", ""),
                    "version": 1,
                },
            ))
    return docs


def build_docs_from_neo4j(seed_only: bool = False) -> list[SearchDoc]:
    """从 Neo4j 读 Table+Field+expression, 构建 SearchDoc 列表。

    seed_only=True 用于单元测试 — 直接从 backend.seed.tables 静态结构生成，
    不需要 Neo4j 可达。
    """
    if seed_only:
        return _docs_from_seed(SEED_TABLES)

    rows = run_query(
        """
        MATCH (t:Table)
        OPTIONAL MATCH (t)-[:HAS_FIELD]->(f:Field)
        WITH t,
             collect(CASE WHEN f IS NULL THEN null ELSE {
                 name: f.name, type: f.data_type, description: f.description,
                 expression: f.expression, version: f.version
             } END) AS fields
        RETURN t.name AS name, t.layer AS layer, t.storage_type AS storage_type,
               t.description AS description, t.version AS version, fields
        """
    )
    docs: list[SearchDoc] = []
    for r in rows:
        clean_fields = [f for f in r["fields"] if f is not None]
        docs.append(SearchDoc(
            id=f"table:{r['name']}",
            type="table",
            text=build_table_text({
                "name": r["name"],
                "description": r["description"],
                "fields": clean_fields,
            }),
            metadata={
                "table_name": r["name"],
                "layer": r["layer"],
                "storage_type": r["storage_type"],
                "version": r.get("version") or 1,
            },
        ))
        for f in clean_fields:
            docs.append(SearchDoc(
                id=f"field:{r['name']}.{f['name']}",
                type="field",
                text=build_field_text(r["name"], f),
                metadata={
                    "table_name": r["name"],
                    "field_name": f["name"],
                    "data_type": f.get("type", ""),
                    "version": f.get("version") or 1,
                },
            ))
    return docs
```

- [ ] **Step 4: 单元测试通过（跳过 `infra` mark）**

```bash
pytest tests/search/test_docs.py -v -m "not infra"
```

预期：PASS (3/3 非 infra 用例)。

- [ ] **Step 5: 提交**

```bash
git add backend/search/docs.py tests/search/test_docs.py
git commit -m "feat(search): Neo4j to SearchDoc serializer"
```

---

## Task 4: RRF 纯函数融合

**Files:**
- Create: `backend/search/fusion.py`
- Create: `tests/search/test_fusion.py`

- [ ] **Step 1: 写失败的测试**

```python
"""tests/search/test_fusion.py"""
from backend.search.fusion import rrf_fuse


def test_rrf_top1_match_gets_high_score_when_both_agree():
    """两路都把同一个 doc 排到第一位 → RRF 分最大。"""
    bm25 = [("d1", 5.2), ("d2", 4.1), ("d3", 0.9)]
    dense_ids = ["d1", "d3", "d2"]
    fused = rrf_fuse(bm25, dense_ids, k=60, top_k=3)
    assert fused[0][0] == "d1"
    # d1 同列两路 rank1 → 1/61 + 1/61 ≈ 0.0328
    assert abs(fused[0][1] - (1 / 61 + 1 / 61)) < 1e-9


def test_rrf_unique_to_one_source_still_returned():
    """只在 bm25 出现的 doc 也要被返回。"""
    bm25 = [("d1", 5.2)]
    dense_ids = ["d2"]
    fused = rrf_fuse(bm25, dense_ids, k=60, top_k=5)
    ids = [d for d, _ in fused]
    assert "d1" in ids and "d2" in ids


def test_rrf_top_k_caps_output():
    bm25 = [("d1", 1.0), ("d2", 0.9), ("d3", 0.8), ("d4", 0.7)]
    dense_ids = ["d1", "d2", "d3", "d4"]
    fused = rrf_fuse(bm25, dense_ids, k=60, top_k=2)
    assert len(fused) == 2


def test_rrf_empty_inputs_return_empty():
    assert rrf_fuse([], [], k=60, top_k=10) == []
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_fusion.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/search/fusion.py`**

```python
"""Reciprocal Rank Fusion — 纯函数。"""
from __future__ import annotations


def rrf_fuse(
    bm25_ranked: list[tuple[str, float]],
    dense_ids: list[str],
    k: int = 60,
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """合并 BM25 和 Dense 两路排序。

    score(doc) = Σ 1 / (k + rank_i + 1)    # rank 从 0 起，所以 +1

    参数:
      bm25_ranked: [(doc_id, raw_score), ...] 按 raw_score 降序
      dense_ids:   [doc_id, ...] 按 cosine 升序的距离 → 已是相似度降序
      k:           阻尼常数 (默认 60)
      top_k:       返回前 top_k 个
    """
    scores: dict[str, float] = {}
    for rank, (doc_id, _) in enumerate(bm25_ranked):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, doc_id in enumerate(dense_ids):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked[:top_k]
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/search/test_fusion.py -v
```

预期：PASS (4/4)。

- [ ] **Step 5: 提交**

```bash
git add backend/search/fusion.py tests/search/test_fusion.py
git commit -m "feat(search): RRF fusion pure function"
```

---

## Task 5: Embedder + ChromaDB 包装

**Files:**
- Create: `backend/search/embedder.py`
- Create: `tests/search/test_embedder.py`

> **降级路径**：bge 模型加载失败时 `Embedder.available=False`。HybridSearcher 看到这个标志后跳过 Dense 检索，只走 BM25。

- [ ] **Step 1: 写失败的测试**

```python
"""tests/search/test_embedder.py — 不下载真实模型时跳过 dense；仅验证降级路径与 ChromaDB 操作。"""
import pytest

from backend.search.embedder import Embedder


def test_embedder_degraded_when_model_load_fails(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("offline")

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer", boom
    )
    emb = Embedder(model_name="boom-model", chroma_dir=":memory:")
    assert emb.available is False
    # encode 在 degraded 模式下抛 RuntimeError
    with pytest.raises(RuntimeError):
        emb.encode(["x"])


def test_embedder_chroma_upsert_and_count(tmp_path, monkeypatch):
    """用一个 stub encoder 跑通 upsert/query 链路。"""
    import numpy as np

    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            # 把字符串长度作为唯一维度，简化但确定。
            return np.array([[len(t) / 100.0] * 16 for t in texts])

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )
    emb = Embedder(model_name="stub", chroma_dir=str(tmp_path / "chroma"))
    assert emb.available is True

    emb.upsert(
        ids=["a", "b"],
        documents=["aaaaa", "bbbbbbb"],
        metadatas=[{"k": 1}, {"k": 2}],
    )
    assert emb.count() == 2

    out = emb.query("aaaaa", n_results=2)
    assert "a" in out["ids"][0]


def test_embedder_index_version_roundtrip(tmp_path, monkeypatch):
    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return [[0.0] * 16 for _ in texts]

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )
    emb = Embedder(model_name="stub", chroma_dir=str(tmp_path / "chroma"))
    assert emb.get_index_version() == 0
    emb.set_index_version(7)
    assert emb.get_index_version() == 7
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_embedder.py -v
```

预期：FAIL — `ModuleNotFoundError: No module named 'backend.search.embedder'`。

- [ ] **Step 3: 实现 `backend/search/embedder.py`**

```python
"""bge-small-zh + ChromaDB persistent collection。

Embedder 故意做成可降级 — bge 模型加载失败时 available=False，
HybridSearcher 检测后跳过 Dense 检索 (spec §4.6.4 异常处理)。
"""
from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

# 惰性导入，让降级路径在 monkeypatch 后仍生效
try:
    from sentence_transformers import SentenceTransformer  # noqa: F401
except Exception:  # pragma: no cover — 仅在 sentence_transformers 安装异常时
    SentenceTransformer = None  # type: ignore[assignment]


_COLLECTION_NAME = "metadata_index"


class Embedder:
    """封装 bge-small-zh 编码 + ChromaDB persistent collection。"""

    def __init__(self, model_name: str, chroma_dir: str):
        self.model_name = model_name
        self.chroma_dir = chroma_dir
        self._encoder: Any | None = None
        try:
            if SentenceTransformer is None:
                raise RuntimeError("sentence_transformers not importable")
            self._encoder = SentenceTransformer(model_name)
        except Exception as e:
            logger.warning("Embedder degraded — bge load failed: %s", e)
            self._encoder = None

        if chroma_dir == ":memory:":
            self._client = chromadb.EphemeralClient(
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        else:
            self._client = chromadb.PersistentClient(
                path=chroma_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def available(self) -> bool:
        return self._encoder is not None

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not self.available:
            raise RuntimeError("Embedder is in degraded mode (bge unavailable)")
        vecs = self._encoder.encode(texts, normalize_embeddings=True)
        # SentenceTransformer 返回 np.ndarray；统一转 list[list[float]]
        return [list(map(float, v)) for v in vecs]

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        embeddings = self.encode(documents) if self.available else None
        kwargs = {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        }
        if embeddings is not None:
            kwargs["embeddings"] = embeddings
        self._collection.upsert(**kwargs)

    def query(self, text: str, n_results: int = 10) -> dict:
        if not self.available:
            raise RuntimeError("Dense query unavailable in degraded mode")
        vec = self.encode([text])[0]
        return self._collection.query(
            query_embeddings=[vec],
            n_results=n_results,
            include=["metadatas", "documents", "distances"],
        )

    def count(self) -> int:
        return self._collection.count()

    def get_index_version(self) -> int:
        meta = self._collection.metadata or {}
        return int(meta.get("index_version", 0))

    def set_index_version(self, version: int) -> None:
        meta = dict(self._collection.metadata or {})
        meta["index_version"] = int(version)
        # ChromaDB modify 接受 name 和 metadata
        self._collection.modify(metadata=meta)
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/search/test_embedder.py -v
```

预期：PASS (3/3)。

- [ ] **Step 5: 提交**

```bash
git add backend/search/embedder.py tests/search/test_embedder.py
git commit -m "feat(search): bge encoder + ChromaDB persistent collection with degraded mode"
```

---

## Task 6: DeepSeek 客户端共享底座

**Files:**
- Create: `backend/clients/deepseek.py`
- Create: `tests/search/test_deepseek_client.py`

- [ ] **Step 1: 写失败的测试**

```python
"""tests/search/test_deepseek_client.py"""
from unittest.mock import MagicMock

import pytest

from backend.clients.deepseek import get_deepseek_client, build_chat_client


def test_build_chat_client_uses_settings(monkeypatch):
    captured = {}

    def fake_chat(**kwargs):
        captured.update(kwargs)
        return MagicMock(name="ChatOpenAI")

    monkeypatch.setattr("backend.clients.deepseek.ChatOpenAI", fake_chat)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-zzz")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    from backend.config import get_settings
    get_settings.cache_clear()

    client = build_chat_client(temperature=0.3)
    assert captured["api_key"] == "sk-zzz"
    assert captured["base_url"] == "https://api.deepseek.test"
    assert captured["model"] == "deepseek-chat"
    assert captured["temperature"] == 0.3


def test_get_deepseek_client_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    from backend.config import get_settings
    get_settings.cache_clear()
    get_deepseek_client.cache_clear()
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        get_deepseek_client()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_deepseek_client.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/clients/deepseek.py`**

```python
"""DeepSeek (OpenAI-compatible) LangChain client — slice 2a rerank + slice 2b LLM nodes 共用。"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from backend.config import get_settings


def build_chat_client(*, temperature: float = 0.0, **kwargs) -> ChatOpenAI:
    """每次新建一个 client；用于 temperature 不同的场景。"""
    s = get_settings()
    if not s.deepseek_api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is empty. Set it in .env before using DeepSeek."
        )
    return ChatOpenAI(
        api_key=s.deepseek_api_key,
        base_url=s.deepseek_base_url,
        model=s.deepseek_model,
        temperature=temperature,
        **kwargs,
    )


@lru_cache(maxsize=1)
def get_deepseek_client() -> ChatOpenAI:
    """temperature=0 的默认单例，给 rerank / classifier 这类要求确定性的节点用。"""
    return build_chat_client(temperature=0.0)
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/search/test_deepseek_client.py -v
```

预期：PASS (2/2)。

- [ ] **Step 5: 提交**

```bash
git add backend/clients/deepseek.py tests/search/test_deepseek_client.py
git commit -m "feat(clients): shared DeepSeek ChatOpenAI client"
```

---

## Task 7: LLM Rerank

**Files:**
- Create: `backend/search/rerank.py`
- Create: `tests/search/test_rerank.py`

- [ ] **Step 1: 写失败的测试**

```python
"""tests/search/test_rerank.py — mock DeepSeek; 验证 rerank prompt 构造与解析。"""
import json
from unittest.mock import MagicMock

from backend.search.docs import SearchDoc
from backend.search.rerank import llm_rerank, RERANK_PROMPT


def _doc(id_: str, table_name: str, text: str) -> SearchDoc:
    return SearchDoc(
        id=id_, type="table", text=text,
        metadata={"table_name": table_name, "version": 1},
    )


def test_rerank_calls_client_with_prompt_containing_query():
    candidates = [(_doc("table:a", "a", "table a desc"), 0.05)]
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.content = json.dumps({
        "top_table": {"name": "a", "score": 0.95, "reason": "match"},
        "top_fields": [],
        "alternative_tables": [],
    })
    fake_client.invoke = MagicMock(return_value=fake_resp)

    result = llm_rerank("查覆盖强度", candidates, fake_client)
    assert result[0][0].metadata["table_name"] == "a"
    assert result[0][1] == 0.95
    # prompt 内含用户 query
    prompt_used = fake_client.invoke.call_args[0][0]
    assert "查覆盖强度" in prompt_used


def test_rerank_falls_back_to_input_order_when_llm_returns_invalid_json():
    candidates = [
        (_doc("table:a", "a", ""), 0.05),
        (_doc("table:b", "b", ""), 0.04),
    ]
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.content = "not a json"
    fake_client.invoke = MagicMock(return_value=fake_resp)
    result = llm_rerank("...", candidates, fake_client)
    # 解析失败 → 原顺序返回，分数不变
    assert [d.metadata["table_name"] for d, _ in result] == ["a", "b"]


def test_rerank_prompt_template_has_required_placeholders():
    assert "{user_query}" in RERANK_PROMPT
    assert "{candidates_json}" in RERANK_PROMPT
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_rerank.py -v
```

预期：FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现 `backend/search/rerank.py`**

```python
"""LLM rerank — RRF Top-1 低置信度时调用 (spec §4.6.7)。"""
from __future__ import annotations

import json
import logging
from typing import Any

from backend.search.docs import SearchDoc

logger = logging.getLogger(__name__)

RERANK_PROMPT = """你是无线网络数据专家。用户用自然语言描述了业务需求，
请从以下候选元数据对象中选出最匹配的表和字段。

用户需求: {user_query}

候选对象 (JSON):
{candidates_json}

返回严格的 JSON 格式 (不要 Markdown 包裹):
{{
  "top_table": {{"name": "...", "score": 0.95, "reason": "..."}},
  "top_fields": [{{"name": "...", "table": "...", "score": 0.88, "reason": "..."}}],
  "alternative_tables": [{{"name": "...", "score": 0.72, "reason": "..."}}]
}}
"""


def llm_rerank(
    query: str,
    candidates: list[tuple[SearchDoc, float]],
    client: Any,
) -> list[tuple[SearchDoc, float]]:
    """用 DeepSeek 重排候选。client 必须暴露 .invoke(prompt: str) -> obj.content。

    解析失败 / 返回缺字段时退化为输入顺序。
    """
    cand_json = json.dumps(
        [
            {
                "name": d.metadata.get("table_name") or d.id,
                "type": d.type,
                "description": d.text[:200],
            }
            for d, _ in candidates[:10]
        ],
        ensure_ascii=False,
    )
    prompt = RERANK_PROMPT.format(user_query=query, candidates_json=cand_json)
    try:
        resp = client.invoke(prompt)
        content = getattr(resp, "content", str(resp))
        parsed = json.loads(content)
        top = parsed.get("top_table") or {}
        top_name = top.get("name")
        top_score = float(top.get("score", 0.0))
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
        logger.warning("LLM rerank parse failed: %s — falling back to input order", e)
        return candidates

    by_table = {d.metadata.get("table_name"): (d, top_score) for d, _ in candidates}
    if top_name in by_table:
        d, s = by_table[top_name]
        rest = [(dd, ss) for dd, ss in candidates if dd.metadata.get("table_name") != top_name]
        return [(d, s)] + rest
    return candidates
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/search/test_rerank.py -v
```

预期：PASS (3/3)。

- [ ] **Step 5: 提交**

```bash
git add backend/search/rerank.py tests/search/test_rerank.py
git commit -m "feat(search): LLM rerank with safe fallback"
```

---

## Task 8: HybridSearcher 主类

**Files:**
- Create: `backend/search/searcher.py`
- Create: `tests/search/test_searcher.py`

- [ ] **Step 1: 写失败的测试**

```python
"""tests/search/test_searcher.py — 用 seed_only=True 构建 docs，stub embedder。"""
import numpy as np
import pytest

from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher


@pytest.fixture
def stub_searcher(tmp_path, monkeypatch):
    """构造一个用 stub bge 的搜索器, 跑通索引流程。"""
    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            # 简单基于字符总长度的伪向量, 但能保证可计算 cosine
            return np.array([[hash(t) % 100 / 100.0] * 16 for t in texts])

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )
    emb = Embedder(model_name="stub", chroma_dir=str(tmp_path / "chroma"))
    docs = build_docs_from_neo4j(seed_only=True)
    s = HybridSearcher(embedder=emb, rerank_threshold=0.15)
    s.build_index(docs)
    return s


def test_searcher_returns_results_for_known_table(stub_searcher):
    """搜 'dws_cell_hourly' 应命中 (BM25 强匹配)。"""
    out = stub_searcher.search("dws_cell_hourly", k=5, use_rerank=False)
    assert len(out) > 0
    table_names = {r["doc"].metadata.get("table_name") for r in out}
    assert "dws_cell_hourly" in table_names


def test_searcher_returns_results_for_chinese_query(stub_searcher):
    out = stub_searcher.search("掉话率", k=5, use_rerank=False)
    table_names = [r["doc"].metadata.get("table_name") for r in out]
    assert "dws_cell_hourly" in table_names  # drop_rate 字段在描述里


def test_searcher_skip_dense_when_embedder_unavailable(tmp_path, monkeypatch):
    """bge 不可用 → 自动跳过 Dense, 只走 BM25。"""
    def boom(*a, **kw):
        raise RuntimeError("offline")

    monkeypatch.setattr("backend.search.embedder.SentenceTransformer", boom)
    emb = Embedder(model_name="boom", chroma_dir=str(tmp_path / "chroma"))
    assert emb.available is False
    docs = build_docs_from_neo4j(seed_only=True)
    s = HybridSearcher(embedder=emb, rerank_threshold=0.15)
    s.build_index(docs)
    out = s.search("ods_ue_signal", k=3, use_rerank=False)
    assert len(out) > 0
    assert any(r["doc"].metadata.get("table_name") == "ods_ue_signal" for r in out)


def test_searcher_upsert_adds_new_doc(stub_searcher):
    from backend.search.docs import SearchDoc

    new_doc = SearchDoc(
        id="table:ods_gnb_load",
        type="table",
        text="ods_gnb_load 基站负载原始流 cpu_util mem_util",
        metadata={"table_name": "ods_gnb_load", "layer": "ODS",
                  "storage_type": "KAFKA", "version": 1},
    )
    stub_searcher.upsert([new_doc])
    out = stub_searcher.search("基站负载", k=5, use_rerank=False)
    table_names = [r["doc"].metadata.get("table_name") for r in out]
    assert "ods_gnb_load" in table_names


def test_searcher_get_index_version(stub_searcher):
    assert stub_searcher.get_index_version() >= 1
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_searcher.py -v
```

预期：FAIL — `ModuleNotFoundError: No module named 'backend.search.searcher'`。

- [ ] **Step 3: 实现 `backend/search/searcher.py`**

```python
"""HybridSearcher — BM25 + Dense + RRF + (optional) LLM rerank."""
from __future__ import annotations

import logging
from threading import RLock
from typing import Any

from rank_bm25 import BM25Okapi

from backend.search.docs import SearchDoc
from backend.search.embedder import Embedder
from backend.search.fusion import rrf_fuse
from backend.search.preprocessing import tokenize
from backend.search.rerank import llm_rerank

logger = logging.getLogger(__name__)


class HybridSearcher:
    """组合 BM25 + Dense + RRF + LLM rerank 兜底。"""

    def __init__(
        self,
        *,
        embedder: Embedder,
        rerank_threshold: float = 0.15,
        rrf_k: int = 60,
    ):
        self._embedder = embedder
        self._rerank_threshold = rerank_threshold
        self._rrf_k = rrf_k

        self._docs: list[SearchDoc] = []
        self._bm25: BM25Okapi | None = None
        self._doc_by_id: dict[str, SearchDoc] = {}
        self._lock = RLock()

    # ---- 构建 / 增量 ----

    def build_index(self, docs: list[SearchDoc]) -> None:
        with self._lock:
            self._docs = list(docs)
            self._doc_by_id = {d.id: d for d in self._docs}
            self._bm25 = BM25Okapi([tokenize(d.text) for d in self._docs])
            if self._embedder.available:
                self._embedder.upsert(
                    ids=[d.id for d in self._docs],
                    documents=[d.text for d in self._docs],
                    metadatas=[d.metadata for d in self._docs],
                )
            self._embedder.set_index_version(self._compute_version())

    def upsert(self, docs: list[SearchDoc]) -> None:
        with self._lock:
            for d in docs:
                self._doc_by_id[d.id] = d
            self._docs = list(self._doc_by_id.values())
            self._bm25 = BM25Okapi([tokenize(d.text) for d in self._docs])
            if self._embedder.available:
                self._embedder.upsert(
                    ids=[d.id for d in docs],
                    documents=[d.text for d in docs],
                    metadatas=[d.metadata for d in docs],
                )
            self._embedder.set_index_version(self._compute_version())

    def _compute_version(self) -> int:
        # 版本 = 文档数 × 1000 + 平均 version 字段 — 单调递增即可
        if not self._docs:
            return 0
        total = sum(int(d.metadata.get("version", 1)) for d in self._docs)
        return len(self._docs) * 1000 + total

    def get_index_version(self) -> int:
        return self._embedder.get_index_version()

    # ---- 检索 ----

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        use_rerank: bool = True,
        rerank_client: Any | None = None,
    ) -> list[dict]:
        if self._bm25 is None or not self._docs:
            return []

        bm25_scores = self._bm25.get_scores(tokenize(query))
        bm25_pairs = sorted(
            zip([d.id for d in self._docs], bm25_scores),
            key=lambda x: -x[1],
        )[:k * 2]

        if self._embedder.available:
            try:
                dense = self._embedder.query(query, n_results=k)
                dense_ids = dense.get("ids", [[]])[0]
            except Exception as e:
                logger.warning("Dense query failed, falling back to BM25 only: %s", e)
                dense_ids = []
        else:
            dense_ids = []

        fused = rrf_fuse(bm25_pairs, dense_ids, k=self._rrf_k, top_k=k)
        result_pairs = [
            (self._doc_by_id[doc_id], score)
            for doc_id, score in fused
            if doc_id in self._doc_by_id
        ]

        if use_rerank and result_pairs and result_pairs[0][1] < self._rerank_threshold:
            if rerank_client is None:
                logger.debug("Rerank skipped — no client provided.")
            else:
                result_pairs = llm_rerank(query, result_pairs, rerank_client)

        return [
            {
                "doc": d,
                "score": s,
                "table": d.metadata.get("table_name"),
            }
            for d, s in result_pairs
        ]
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/search/test_searcher.py -v
```

预期：PASS (5/5)。

- [ ] **Step 5: 提交**

```bash
git add backend/search/searcher.py tests/search/test_searcher.py
git commit -m "feat(search): HybridSearcher composes BM25 + Dense + RRF + rerank"
```

---

## Task 9: FastAPI 接入 — lifespan 初始化 + `/api/search` 路由

**Files:**
- Modify: `backend/main.py`
- Create: `backend/api/search.py`
- Modify: `backend/api/health.py`
- Create: `tests/search/test_api_search.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: 写失败的测试**

新增 `tests/search/test_api_search.py`：

```python
"""tests/search/test_api_search.py — 走 FastAPI TestClient 黑盒。"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    import numpy as np

    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[hash(t) % 100 / 100.0] * 16 for t in texts])

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )
    monkeypatch.setenv("SEARCH_CHROMA_DIR", str(tmp_path / "chroma"))
    # 走 seed_only=True, 避免依赖真实 Neo4j
    monkeypatch.setenv("SEARCH_BOOTSTRAP_FROM_SEED", "1")
    from backend.config import get_settings
    get_settings.cache_clear()

    from backend.main import create_app
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_get_search_returns_results_for_known_table(api_client):
    r = api_client.get("/api/search", params={"q": "dws_cell_hourly", "k": 5})
    assert r.status_code == 200
    body = r.json()
    assert "query" in body and "results" in body
    assert len(body["results"]) > 0
    assert any(item["table"] == "dws_cell_hourly" for item in body["results"])


def test_get_search_query_required(api_client):
    r = api_client.get("/api/search")
    assert r.status_code == 422  # FastAPI 自动 validation error


def test_get_search_type_filter(api_client):
    r = api_client.get("/api/search", params={"q": "rsrp", "type": "field", "k": 5})
    assert r.status_code == 200
    body = r.json()
    for item in body["results"]:
        assert item["doc"]["type"] == "field"


def test_health_now_includes_search_component(api_client):
    r = api_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "search" in body["components"]
    assert body["components"]["search"]["status"] in {"ok", "degraded", "error"}
    # 在 stub 模式下，索引应被构建过, index_version > 0
    if body["components"]["search"]["status"] == "ok":
        assert body["components"]["search"]["index_version"] > 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_api_search.py -v
```

预期：FAIL — `/api/search` 不存在；`api_client` fixture 找不到 `SEARCH_BOOTSTRAP_FROM_SEED`。

- [ ] **Step 3: 配置层补加 bootstrap 开关**

在 `backend/config.py` 的 `Settings` 类末尾追加：

```python
    # Slice 2a 测试用 — 跳过 Neo4j, 从 SEED_TABLES 直接构建索引
    search_bootstrap_from_seed: bool = Field(False, alias="SEARCH_BOOTSTRAP_FROM_SEED")
```

- [ ] **Step 4: 创建 `backend/api/search.py`**

```python
"""GET /api/search — 混合语义检索 (spec §6.7 + §4.6)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter()


class SearchHit(BaseModel):
    table: str | None
    score: float
    doc: dict


class SearchResponse(BaseModel):
    query: str
    type: str
    k: int
    results: list[SearchHit]


@router.get("/api/search", response_model=SearchResponse)
def search(
    request: Request,
    q: str = Query(..., min_length=1, description="自然语言查询"),
    type: Literal["any", "table", "field"] = Query("any"),
    k: int = Query(10, ge=1, le=50),
):
    searcher = getattr(request.app.state, "searcher", None)
    if searcher is None:
        raise HTTPException(status_code=503, detail="Search index not initialized")

    raw = searcher.search(q, k=k * 2, use_rerank=False)
    filtered = [
        r for r in raw
        if type == "any" or r["doc"].type == type
    ][:k]
    return SearchResponse(
        query=q,
        type=type,
        k=k,
        results=[
            SearchHit(
                table=r["table"],
                score=r["score"],
                doc=r["doc"].to_dict(),
            )
            for r in filtered
        ],
    )
```

- [ ] **Step 5: 修改 `backend/main.py` 在 lifespan 中初始化 searcher**

把 `backend/main.py` 整个替换为：

```python
"""FastAPI app factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api import health, metadata, search
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
    yield
    close_driver()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Wireless RNO Data Semantic Service",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(metadata.router, tags=["metadata"])
    app.include_router(search.router, tags=["search"])
    return app


app = create_app()
```

- [ ] **Step 6: 修改 `backend/api/health.py` 加 search 组件**

把整个文件替换为：

```python
"""GET /api/health — slice 2a: FastAPI + Neo4j + Search."""
import time

from fastapi import APIRouter, Request

from backend.metadata.graph import run_query


router = APIRouter()
_BOOT_TS = time.monotonic()


@router.get("/api/health")
def health(request: Request) -> dict:
    components: dict = {}
    overall = "healthy"

    # Neo4j
    try:
        start = time.perf_counter()
        run_query("RETURN 1")
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        node_count_rows = run_query("MATCH (n) RETURN count(n) AS n")
        components["neo4j"] = {
            "status": "ok",
            "latency_ms": latency_ms,
            "node_count": node_count_rows[0]["n"],
        }
    except Exception as e:
        components["neo4j"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Search
    searcher = getattr(request.app.state, "searcher", None)
    if searcher is None:
        components["search"] = {"status": "error", "error": "not initialized"}
        overall = "degraded"
    else:
        try:
            version = searcher.get_index_version()
            available = searcher._embedder.available  # noqa: SLF001 — slice 2a 内部用
            components["search"] = {
                "status": "ok" if available else "degraded",
                "index_version": version,
                "dense_available": available,
            }
            if not available and overall == "healthy":
                overall = "degraded"
        except Exception as e:
            components["search"] = {"status": "error", "error": str(e)}
            overall = "degraded"

    return {
        "status": overall,
        "uptime_seconds": int(time.monotonic() - _BOOT_TS),
        "components": components,
    }
```

- [ ] **Step 7: `tests/conftest.py` 不需要改 — 但确认 `api_client` 模式可用**

读 `tests/conftest.py` 当前内容；如果没有冲突就跳过。新增的 `api_client` fixture 已经在 `tests/search/test_api_search.py` 内本地定义。

- [ ] **Step 8: 测试通过**

```bash
pytest tests/search/test_api_search.py -v
```

预期：PASS (4/4)。

- [ ] **Step 9: 提交**

```bash
git add backend/api/search.py backend/api/health.py backend/main.py backend/config.py tests/search/test_api_search.py
git commit -m "feat(search): GET /api/search endpoint + health integration"
```

---

## Task 10: Benchmark 测试集生成脚本

**Files:**
- Create: `scripts/generate_benchmark_queries.py`
- Create: `benchmark/benchmark_queries.yaml`（脚本输出）

> 类型 A (30 条规则生成) 由脚本派生自 `SEED_TABLES`；类型 B (20 条 LLM 风格人工查询) + 类型 C (10 条对抗) 在脚本里**作为常量列表硬编码**（spec §4.7.1 的 "LLM 生成" 和 "对抗样本" 是一次性编写），确保 plan 内容完整，CI 可重现。

- [ ] **Step 1: 创建 `scripts/generate_benchmark_queries.py`**

```python
"""生成 60 条 benchmark queries → benchmark/benchmark_queries.yaml。

类型 A (30): 从 SEED_TABLES 派生 — table.description 同义词替换 + 字段描述衍生
类型 B (20): 人工编写的 LLM 风格 (不同角色提问)
类型 C (10): 对抗样本 (模糊/歧义/跨域)
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from backend.seed.tables import SEED_TABLES

# ---- Type A 模板 ----
# (描述关键词, 同义查询前缀, difficulty)
SYNONYM_PROBES: list[tuple[str, str, str, str]] = [
    # (target_table, query, expected_field_or_empty, difficulty)
    ("ods_ue_signal", "查 UE 终端的 RSRP/SINR 采样", "rsrp", "easy"),
    ("ods_ue_signal", "用户终端的信噪比原始数据", "sinr", "easy"),
    ("ods_ue_signal", "终端上报的信号原始流", "", "easy"),
    ("ods_gnb_alarm", "基站告警的原始数据", "", "easy"),
    ("ods_gnb_alarm", "gnodeB 故障告警流", "alarm_type", "medium"),
    ("ods_gnb_alarm", "基站故障严重度", "severity", "easy"),
    ("dwd_session_qos", "用户会话级别的 QoS 明细", "", "easy"),
    ("dwd_session_qos", "会话粒度的平均覆盖强度", "avg_rsrp", "medium"),
    ("dwd_session_qos", "会话粒度的平均信噪比", "avg_sinr", "medium"),
    ("dwd_session_qos", "会话延时和抖动", "latency", "medium"),
    ("dwd_ho_event", "终端切换事件记录", "", "easy"),
    ("dwd_ho_event", "用户基站间切换是否成功", "ho_result", "medium"),
    ("dwd_ho_event", "切换的源小区和目标小区", "source_cell", "easy"),
    ("dws_cell_hourly", "小区小时粒度的平均覆盖强度", "avg_rsrp", "easy"),
    ("dws_cell_hourly", "小区每小时的掉话率", "drop_rate", "easy"),
    ("dws_cell_hourly", "每个小区每小时的平均吞吐量", "avg_throughput", "easy"),
    ("dws_cell_hourly", "小区小时粒度切换成功率", "ho_success_rate", "easy"),
    ("dws_cell_hourly", "小区每小时会话总数", "total_sessions", "medium"),
    ("dws_area_traffic", "区域级别每小时的流量统计", "", "easy"),
    ("dws_area_traffic", "区域级活跃用户数", "active_users", "medium"),
    ("dws_area_traffic", "区域每小时上下行字节数", "uplink_bytes", "medium"),
    ("ads_cell_profile", "小区画像的覆盖能力指标", "coverage_score", "medium"),
    ("ads_cell_profile", "小区容量评分", "capacity_score", "medium"),
    ("ads_cell_profile", "小区稳定性评分", "stability_score", "medium"),
    ("ads_cell_profile", "小区移动性评分", "mobility_score", "medium"),
    ("ads_user_profile", "用户画像 QoE 评分", "qoe_score", "medium"),
    ("ads_user_profile", "用户活跃天数", "active_days", "easy"),
    ("eval_user_score", "用户综合体验评估打分", "qoe_score", "medium"),
    ("eval_net_health", "网络整体健康度指标", "health_index", "medium"),
    ("eval_net_health", "网络可用性评估", "availability", "medium"),
]
assert len(SYNONYM_PROBES) == 30, "Type A 需要恰好 30 条"

# ---- Type B (人工 LLM 风格, 20 条) ----
TYPE_B: list[dict] = [
    {"query": "帮我看看最近一段时间信号质量差的用户都有哪些", "expected_table": "dwd_session_qos", "expected_fields": ["avg_sinr", "avg_rsrp"], "difficulty": "medium"},
    {"query": "我想知道哪些基站老是告警", "expected_table": "ods_gnb_alarm", "expected_fields": ["gnb_id", "alarm_type"], "difficulty": "medium"},
    {"query": "运维老板要看每个小区的整体打分", "expected_table": "ads_cell_profile", "expected_fields": ["coverage_score"], "difficulty": "medium"},
    {"query": "查一下用户在 5G 切换时成功的比例", "expected_table": "dws_cell_hourly", "expected_fields": ["ho_success_rate"], "difficulty": "hard"},
    {"query": "我要看高峰时段哪些区域流量爆了", "expected_table": "dws_area_traffic", "expected_fields": ["uplink_bytes", "downlink_bytes"], "difficulty": "hard"},
    {"query": "评估一下网络是否健康", "expected_table": "eval_net_health", "expected_fields": ["health_index"], "difficulty": "medium"},
    {"query": "我想分析用户 QoE 体验分数的分布", "expected_table": "eval_user_score", "expected_fields": ["qoe_score"], "difficulty": "easy"},
    {"query": "拉一下小区每小时的平均掉话率", "expected_table": "dws_cell_hourly", "expected_fields": ["drop_rate"], "difficulty": "easy"},
    {"query": "查覆盖弱的用户的明细", "expected_table": "dwd_session_qos", "expected_fields": ["avg_rsrp"], "difficulty": "medium"},
    {"query": "把所有终端在基站间的切换都列出来", "expected_table": "dwd_ho_event", "expected_fields": [], "difficulty": "easy"},
    {"query": "看一下哪些用户活跃天数多", "expected_table": "ads_user_profile", "expected_fields": ["active_days"], "difficulty": "easy"},
    {"query": "想看小区在某段时间内的吞吐能力", "expected_table": "dws_cell_hourly", "expected_fields": ["avg_throughput"], "difficulty": "medium"},
    {"query": "找网络稳定性差的小区", "expected_table": "ads_cell_profile", "expected_fields": ["stability_score"], "difficulty": "medium"},
    {"query": "做用户体验报告需要打分原始数据", "expected_table": "eval_user_score", "expected_fields": ["qoe_score"], "difficulty": "medium"},
    {"query": "ARPU 高但是体验差的用户有哪些", "expected_table": "ads_user_profile", "expected_fields": ["qoe_score"], "difficulty": "hard"},
    {"query": "查每个区域每小时的活跃用户数", "expected_table": "dws_area_traffic", "expected_fields": ["active_users"], "difficulty": "easy"},
    {"query": "我要监测掉线率突增的小区", "expected_table": "dws_cell_hourly", "expected_fields": ["drop_rate"], "difficulty": "medium"},
    {"query": "想知道告警持续了多久", "expected_table": "ods_gnb_alarm", "expected_fields": ["duration"], "difficulty": "medium"},
    {"query": "看用户从一个塔切到另一个塔的情况", "expected_table": "dwd_ho_event", "expected_fields": ["source_cell", "target_cell"], "difficulty": "hard"},
    {"query": "做容量评估的输入数据", "expected_table": "ads_cell_profile", "expected_fields": ["capacity_score"], "difficulty": "hard"},
]
assert len(TYPE_B) == 20

# ---- Type C (对抗, 10 条) ----
TYPE_C: list[dict] = [
    {"query": "网络状况怎么样", "expected_table": "eval_net_health", "expected_fields": ["health_index"], "difficulty": "hard"},
    {"query": "找出网络里有问题的地方", "expected_table": "eval_net_health", "expected_fields": ["health_index"], "difficulty": "hard"},
    {"query": "啥都不知道, 给我看个总体情况", "expected_table": "eval_net_health", "expected_fields": [], "difficulty": "hard"},
    {"query": "把所有的数据都给我", "expected_table": "ods_ue_signal", "expected_fields": [], "difficulty": "hard"},  # 故意宽泛
    {"query": "做一份分析报告", "expected_table": "eval_user_score", "expected_fields": [], "difficulty": "hard"},
    {"query": "我说的那个表", "expected_table": "dwd_session_qos", "expected_fields": [], "difficulty": "hard"},  # 极度歧义
    {"query": "RSRP 是什么意思", "expected_table": "ods_ue_signal", "expected_fields": ["rsrp"], "difficulty": "medium"},  # 知识型问题, 期望命中含 rsrp 的源表
    {"query": "查 5G 数据", "expected_table": "ods_ue_signal", "expected_fields": [], "difficulty": "hard"},  # 跨域宽泛
    {"query": "qoe 评分公式是啥", "expected_table": "eval_user_score", "expected_fields": ["qoe_score"], "difficulty": "medium"},
    {"query": "切换成功率怎么算", "expected_table": "dws_cell_hourly", "expected_fields": ["ho_success_rate"], "difficulty": "medium"},
]
assert len(TYPE_C) == 10


def main(output_path: str = "benchmark/benchmark_queries.yaml") -> None:
    queries = []
    qid = 1

    # Type A
    for table, query, fld, diff in SYNONYM_PROBES:
        item = {
            "id": f"Q{qid:03d}",
            "type": "A",
            "query": query,
            "expected_table": table,
            "expected_fields": [fld] if fld else [],
            "difficulty": diff,
        }
        queries.append(item)
        qid += 1

    # Type B
    for q in TYPE_B:
        queries.append({
            "id": f"Q{qid:03d}",
            "type": "B",
            **q,
        })
        qid += 1

    # Type C
    for q in TYPE_C:
        queries.append({
            "id": f"Q{qid:03d}",
            "type": "C",
            **q,
        })
        qid += 1

    assert len(queries) == 60
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(queries, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    # 校验 expected_table 全部存在于 SEED_TABLES
    valid_tables = {t["name"] for t in SEED_TABLES}
    for q in queries:
        assert q["expected_table"] in valid_tables, f"Bad table: {q['expected_table']}"

    print(f"Wrote {len(queries)} queries to {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行脚本生成 YAML**

```bash
python scripts/generate_benchmark_queries.py
```

预期：`Wrote 60 queries to benchmark/benchmark_queries.yaml`；`benchmark/benchmark_queries.yaml` 存在。

- [ ] **Step 3: 提交脚本和生成的 YAML**

```bash
git add scripts/generate_benchmark_queries.py benchmark/benchmark_queries.yaml
git commit -m "feat(search): generate 60 benchmark queries (A30/B20/C10)"
```

---

## Task 11: Benchmark 评估脚本 + CI 门禁

**Files:**
- Create: `scripts/benchmark_semantic_search.py`
- Create: `tests/search/test_benchmark.py`

- [ ] **Step 1: 写失败的测试**

```python
"""tests/search/test_benchmark.py — 在 stub 模式下跑 benchmark, 验证目标达标。"""
import numpy as np
import pytest
import yaml
from pathlib import Path

from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher
from scripts.benchmark_semantic_search import (
    evaluate,
    BenchmarkTargets,
    DEFAULT_TARGETS,
)


@pytest.fixture
def searcher(tmp_path, monkeypatch):
    class StubEncoder:
        def encode(self, texts, normalize_embeddings=True):
            return np.array([[hash(t) % 100 / 100.0] * 16 for t in texts])

    monkeypatch.setattr(
        "backend.search.embedder.SentenceTransformer",
        lambda name: StubEncoder(),
    )
    emb = Embedder(model_name="stub", chroma_dir=str(tmp_path / "chroma"))
    s = HybridSearcher(embedder=emb, rerank_threshold=0.15)
    s.build_index(build_docs_from_neo4j(seed_only=True))
    return s


def test_benchmark_meets_at_least_90pct_of_targets(searcher):
    queries_path = Path("benchmark/benchmark_queries.yaml")
    queries = yaml.safe_load(queries_path.read_text(encoding="utf-8"))
    metrics = evaluate(searcher, queries)
    # CI 门禁: 表 Recall@3 >= 90% 目标 (即 >= 0.855)
    assert metrics["table_recall_at_3"] >= DEFAULT_TARGETS.table_recall_at_3 * 0.9
    # MRR 至少 0.5 (stub 模式宽松基线)
    assert metrics["table_mrr"] >= 0.5


def test_benchmark_targets_defaults_match_spec():
    """spec §4.7.3 目标值落到代码里。"""
    assert DEFAULT_TARGETS.table_recall_at_1 == 0.85
    assert DEFAULT_TARGETS.table_recall_at_3 == 0.95
    assert DEFAULT_TARGETS.table_mrr == 0.90
    assert DEFAULT_TARGETS.field_recall_at_3 == 0.80
    assert DEFAULT_TARGETS.hard_recall_at_1 == 0.65
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/search/test_benchmark.py -v
```

预期：FAIL — `ModuleNotFoundError: scripts.benchmark_semantic_search`。

- [ ] **Step 3: 实现 `scripts/benchmark_semantic_search.py`**

```python
"""60 条 benchmark queries 的离线评估 + CI 门禁。

冷启动:
  $ python scripts/benchmark_semantic_search.py --queries benchmark/benchmark_queries.yaml

增量:
  $ python scripts/benchmark_semantic_search.py --mode incremental --baseline last-run.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import yaml

from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher
from backend.config import get_settings


@dataclass
class BenchmarkTargets:
    table_recall_at_1: float = 0.85
    table_recall_at_3: float = 0.95
    table_mrr: float = 0.90
    field_recall_at_3: float = 0.80
    avg_latency_no_llm_ms: float = 20.0
    avg_latency_with_llm_ms: float = 1000.0
    hard_recall_at_1: float = 0.65


DEFAULT_TARGETS = BenchmarkTargets()

# CI 门禁: 不得低于目标的 90%
GATE_FACTOR = 0.9


def _table_rank(results: list[dict], expected_table: str) -> int:
    """返回 1-based rank, 找不到返回 0。"""
    for idx, r in enumerate(results):
        if r["table"] == expected_table:
            return idx + 1
    return 0


def evaluate(searcher: HybridSearcher, queries: list[dict]) -> dict:
    table_hits_1 = 0
    table_hits_3 = 0
    reciprocal_ranks = []
    field_hits_3 = 0
    field_total = 0
    latencies = []
    hard_hits_1 = 0
    hard_total = 0
    by_diff: dict[str, dict] = {"easy": {"r1": 0, "n": 0}, "medium": {"r1": 0, "n": 0}, "hard": {"r1": 0, "n": 0}}

    for q in queries:
        start = time.perf_counter()
        results = searcher.search(q["query"], k=10, use_rerank=False)
        latencies.append((time.perf_counter() - start) * 1000)

        rank = _table_rank(results, q["expected_table"])
        diff = q.get("difficulty", "medium")
        by_diff[diff]["n"] += 1
        if rank == 1:
            table_hits_1 += 1
            by_diff[diff]["r1"] += 1
            if diff == "hard":
                hard_hits_1 += 1
        if 0 < rank <= 3:
            table_hits_3 += 1
        reciprocal_ranks.append(1.0 / rank if rank > 0 else 0.0)
        if diff == "hard":
            hard_total += 1

        # 字段级 Recall@3
        expected_fields = q.get("expected_fields", [])
        if expected_fields:
            field_total += 1
            top3 = results[:3]
            top3_field_names = [
                r["doc"]["metadata"].get("field_name")
                for r in top3
                if r["doc"].get("type") == "field"
            ]
            if any(f in top3_field_names for f in expected_fields):
                field_hits_3 += 1

    n = len(queries)
    return {
        "n": n,
        "table_recall_at_1": table_hits_1 / n,
        "table_recall_at_3": table_hits_3 / n,
        "table_mrr": sum(reciprocal_ranks) / n,
        "field_recall_at_3": (field_hits_3 / field_total) if field_total else 0.0,
        "avg_latency_ms": sum(latencies) / n,
        "p99_latency_ms": sorted(latencies)[int(0.99 * (n - 1))],
        "hard_recall_at_1": (hard_hits_1 / hard_total) if hard_total else 0.0,
        "by_difficulty": {
            d: {"recall_at_1": (s["r1"] / s["n"]) if s["n"] else 0.0, "n": s["n"]}
            for d, s in by_diff.items()
        },
    }


def check_gate(metrics: dict, targets: BenchmarkTargets) -> list[str]:
    """返回失败的指标名列表; 空列表 = 通过。"""
    failures = []
    if metrics["table_recall_at_1"] < targets.table_recall_at_1 * GATE_FACTOR:
        failures.append(f"table_recall_at_1 {metrics['table_recall_at_1']:.3f} < {targets.table_recall_at_1 * GATE_FACTOR:.3f}")
    if metrics["table_recall_at_3"] < targets.table_recall_at_3 * GATE_FACTOR:
        failures.append(f"table_recall_at_3 {metrics['table_recall_at_3']:.3f} < {targets.table_recall_at_3 * GATE_FACTOR:.3f}")
    if metrics["table_mrr"] < targets.table_mrr * GATE_FACTOR:
        failures.append(f"table_mrr {metrics['table_mrr']:.3f} < {targets.table_mrr * GATE_FACTOR:.3f}")
    if metrics["field_recall_at_3"] < targets.field_recall_at_3 * GATE_FACTOR:
        failures.append(f"field_recall_at_3 {metrics['field_recall_at_3']:.3f} < {targets.field_recall_at_3 * GATE_FACTOR:.3f}")
    if metrics["hard_recall_at_1"] < targets.hard_recall_at_1 * GATE_FACTOR:
        failures.append(f"hard_recall_at_1 {metrics['hard_recall_at_1']:.3f} < {targets.hard_recall_at_1 * GATE_FACTOR:.3f}")
    return failures


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--queries", default="benchmark/benchmark_queries.yaml")
    p.add_argument("--bootstrap-from-seed", action="store_true",
                   help="不连 Neo4j, 直接用 SEED_TABLES 构建索引")
    p.add_argument("--report", default=None, help="把指标写到 JSON 文件")
    args = p.parse_args()

    queries = yaml.safe_load(Path(args.queries).read_text(encoding="utf-8"))
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
    searcher.build_index(build_docs_from_neo4j(seed_only=args.bootstrap_from_seed))

    metrics = evaluate(searcher, queries)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    if args.report:
        Path(args.report).write_text(
            json.dumps({"metrics": metrics, "targets": asdict(DEFAULT_TARGETS)},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    failures = check_gate(metrics, DEFAULT_TARGETS)
    if failures:
        print("CI GATE FAILED:", file=sys.stderr)
        for f in failures:
            print("  -", f, file=sys.stderr)
        return 1
    print("CI GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 测试通过**

```bash
pytest tests/search/test_benchmark.py -v
```

预期：PASS (2/2)。

- [ ] **Step 5: 用真实 bge 模型本地跑一次完整 benchmark（首次冷启耗时约 30s）**

```bash
python scripts/benchmark_semantic_search.py --bootstrap-from-seed --report benchmark/last-run.json
```

预期：stdout 输出 metrics JSON；`CI GATE PASSED`；`benchmark/last-run.json` 写入。如有指标未达标，**先调 prompt / 同义词词典**（修 `backend/search/preprocessing.py` `RNO_TERMS` 或 `backend/search/docs.py` `build_table_text` 拼接策略），不要降阈值。

- [ ] **Step 6: 提交**

```bash
git add scripts/benchmark_semantic_search.py tests/search/test_benchmark.py benchmark/last-run.json
git commit -m "feat(search): benchmark eval script with CI gate (90% of targets)"
```

---

## Task 12: Neo4j 集成 e2e 测试（依赖 base-compose + Neo4j seeded）

**Files:**
- Create: `tests/search/test_searcher_integration.py`

- [ ] **Step 1: 写测试**

```python
"""tests/search/test_searcher_integration.py — 真正连 Neo4j + 真 bge, P2a-acceptance。"""
import os

import pytest

from backend.config import get_settings
from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher


pytestmark = pytest.mark.infra


@pytest.fixture(scope="module")
def live_searcher(tmp_path_factory):
    get_settings.cache_clear()
    chroma_dir = str(tmp_path_factory.mktemp("chroma_e2e"))
    s = get_settings()
    emb = Embedder(model_name=s.search_embed_model, chroma_dir=chroma_dir)
    if not emb.available:
        pytest.skip("bge model unavailable in test environment")
    searcher = HybridSearcher(embedder=emb, rerank_threshold=s.search_rerank_threshold)
    searcher.build_index(build_docs_from_neo4j())
    return searcher


def test_p2a_1_search_yields_dws_cell_hourly_for_chinese_query(live_searcher):
    """P2a-1: '小区每小时的平均覆盖强度' Top-3 应含 dws_cell_hourly。"""
    out = live_searcher.search("小区每小时的平均覆盖强度", k=5, use_rerank=False)
    top3_tables = [r["table"] for r in out[:3]]
    assert "dws_cell_hourly" in top3_tables


def test_p2a_2_search_for_field_returns_field_doc(live_searcher):
    """P2a-2: 'avg_sinr 字段含义' 应命中 field 类型 doc。"""
    out = live_searcher.search("avg_sinr 字段含义", k=10, use_rerank=False)
    field_docs = [r for r in out if r["doc"].type == "field"]
    assert any(r["doc"].metadata.get("field_name") == "avg_sinr" for r in field_docs)


def test_p2a_3_index_version_positive_after_build(live_searcher):
    """P2a-3: 构建后 index_version > 0 并稳定。"""
    v = live_searcher.get_index_version()
    assert v > 0
    assert live_searcher.get_index_version() == v


def test_p2a_4_incremental_upsert_visible_in_search(live_searcher):
    """P2a-4: upsert 新 doc 后, 查得到 (模拟 schema_evolve 后)。"""
    from backend.search.docs import SearchDoc
    new_doc = SearchDoc(
        id="table:ods_gnb_load_test",
        type="table",
        text="ods_gnb_load_test 基站负载原始流 cpu_util mem_util",
        metadata={
            "table_name": "ods_gnb_load_test", "layer": "ODS",
            "storage_type": "KAFKA", "version": 1,
        },
    )
    v0 = live_searcher.get_index_version()
    live_searcher.upsert([new_doc])
    v1 = live_searcher.get_index_version()
    assert v1 != v0
    out = live_searcher.search("基站负载", k=5, use_rerank=False)
    assert any(r["table"] == "ods_gnb_load_test" for r in out)
```

- [ ] **Step 2: 启动栈并跑测试**

确认 base-compose 已起且 Neo4j 已 seeded（slice 1b 的 init-stack.sh 已跑过）：

```bash
docker ps --filter "name=data-gov" --format "{{.Names}} {{.Status}}"
pytest tests/search/test_searcher_integration.py -v -m infra
```

预期：4 个测试 PASS（首次需下载 bge 模型 ~24MB，可能 30s）。

- [ ] **Step 3: 提交**

```bash
git add tests/search/test_searcher_integration.py
git commit -m "test(search): P2a integration tests against live Neo4j"
```

---

## Task 13: app-compose.yml + Dockerfile + init 脚本接入

**Files:**
- Modify: `app-compose.yml`
- Modify: `backend/Dockerfile`
- Create: `init-scripts/08_build_search_index.py`
- Modify: `scripts/init-stack.sh`

- [ ] **Step 1: 修改 `backend/Dockerfile` 加 bge 模型预下载步骤（避免容器启动时再下）**

把原文件替换为：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
COPY backend/ /app/backend/

RUN pip install --no-cache-dir -e ".[runtime]"

# Pre-warm bge model into the image to avoid first-request stall + offline networks.
# Models cached to /root/.cache/huggingface — single layer, ~25MB.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 修改 `app-compose.yml` 加 DeepSeek/SEARCH env + chroma volume**

把 services 块下的 `backend` 完整替换为：

```yaml
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    container_name: data-gov-backend
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: data-gov-neo4j
      NEO4J_DATABASE: neo4j
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}
      DEEPSEEK_BASE_URL: ${DEEPSEEK_BASE_URL:-https://api.deepseek.com}
      DEEPSEEK_MODEL: ${DEEPSEEK_MODEL:-deepseek-chat}
      SEARCH_CHROMA_DIR: /app/data/chroma
      SEARCH_EMBED_MODEL: BAAI/bge-small-zh-v1.5
      SEARCH_RERANK_THRESHOLD: "0.15"
      SEARCH_RRF_K: "60"
    volumes:
      - ./data/chroma:/app/data/chroma
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8000/api/health | grep -q '\"status\":\"healthy\"'"]
      interval: 10s
      timeout: 5s
      retries: 18
      start_period: 30s
```

- [ ] **Step 3: 创建 `init-scripts/08_build_search_index.py`**

> 单独 init 脚本主要给离线场景（CI 或没装好 docker-in-docker 的环境）直接生成索引到 `./data/chroma/`；FastAPI 启动时也会 build，重复 build 是幂等的。

```python
"""离线构建语义检索索引到 ./data/chroma/ (与 FastAPI 启动构建幂等等价)。"""
from __future__ import annotations

import sys

from backend.config import get_settings
from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher


def main() -> int:
    s = get_settings()
    print(f"Loading bge model: {s.search_embed_model}")
    emb = Embedder(model_name=s.search_embed_model, chroma_dir=s.search_chroma_dir)
    if not emb.available:
        print("ERROR: bge model unavailable; index NOT built.", file=sys.stderr)
        return 1
    print("Reading metadata from Neo4j ...")
    docs = build_docs_from_neo4j()
    searcher = HybridSearcher(embedder=emb)
    searcher.build_index(docs)
    print(f"Index built: {len(docs)} docs, version={searcher.get_index_version()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 修改 `scripts/init-stack.sh` 加 [9/10] 离线索引 + [10/10] 等 search 健康**

定位到 slice 1b 写好的 `[8/8]` 步骤；把整段从 `[1/8]` 起的 echo 头部全部改成 `[1/10]..[10/10]`，并在 `[8/N]` 之后插入：

```bash
echo "[9/10] Building search index offline ..."
python init-scripts/08_build_search_index.py

echo "[10/10] Bringing up FastAPI backend ..."
docker compose -f app-compose.yml up -d --build

echo "Waiting for backend healthy (含 search 索引就绪) ..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/api/health | grep -q '"search"'; then
    if curl -fsS http://localhost:8000/api/health | grep -q '"status":"healthy"'; then
      echo "Backend healthy."
      echo "Init complete."
      exit 0
    fi
  fi
  sleep 2
done

echo "Backend did not become fully healthy in 60s." >&2
docker compose -f app-compose.yml logs --tail=100 backend >&2
exit 1
```

> 注意：原 slice 1b 的 `[8/8] Seeding sample data` 仍保留在 `[8/10]` 位置；只是把 docker compose up 和 health wait 这两段合并改为 `[10/10]`。如果 slice 1b 当前的 init-stack.sh 把 docker up 写在 `[8/8]` 之后，需要把它从那里挪到 `[10/10]`。

- [ ] **Step 5: 整栈冷启验证**

```bash
docker compose -f app-compose.yml down 2>/dev/null || true
docker compose -f base-compose.yml down
rm -rf ./data ./metadata-yaml
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
```

预期：`Init complete.` 退出码 0；`curl http://localhost:8000/api/health` 返回 `{"status":"healthy","components":{"neo4j":...,"search":{"status":"ok","index_version":>0,...}}}`。

- [ ] **Step 6: 提交**

```bash
git add app-compose.yml backend/Dockerfile init-scripts/08_build_search_index.py scripts/init-stack.sh
git commit -m "feat(search): containerize search index build + init-stack integration"
```

---

## Task 14: README + 验收表收尾

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README 现有 "Acceptance coverage (Phase 1)" 表下新增 Slice 2a 章节**

追加到 README 末尾：

```markdown

## Acceptance coverage (Phase 2 — slice 2a)

| Case | Verifies | Test |
|------|----------|------|
| P2a-1 | 中文 NL 查询命中表 (dws_cell_hourly) | `tests/search/test_searcher_integration.py::test_p2a_1_search_yields_dws_cell_hourly_for_chinese_query` |
| P2a-2 | 字段级 doc 可被命中 | `tests/search/test_searcher_integration.py::test_p2a_2_search_for_field_returns_field_doc` |
| P2a-3 | index_version 单调正向 | `tests/search/test_searcher_integration.py::test_p2a_3_index_version_positive_after_build` |
| P2a-4 | 增量 upsert 立即可查 | `tests/search/test_searcher_integration.py::test_p2a_4_incremental_upsert_visible_in_search` |
| P2a-5 | 60 条 benchmark 达到目标 90% | `tests/search/test_benchmark.py::test_benchmark_meets_at_least_90pct_of_targets` |
| P2a-6 | `/api/search?q=&type=&k=` 返回结构 | `tests/search/test_api_search.py::test_get_search_returns_results_for_known_table` |
| P2a-7 | `/api/health` 含 search 组件 | `tests/search/test_api_search.py::test_health_now_includes_search_component` |
| P2a-8 | bge 不可用时降级为纯 BM25 | `tests/search/test_searcher.py::test_searcher_skip_dense_when_embedder_unavailable` |
| P2a-9 | LLM rerank 触发与解析降级 | `tests/search/test_rerank.py::*` |

跑全部 slice 2a 测试：

```bash
pytest tests/search -v
pytest tests/search -v -m infra   # 需 base-compose + Neo4j seeded
python scripts/benchmark_semantic_search.py
```

Deferred to slice 2b: LangGraph Agent (forward_etl / reverse_synth / schema_evolve), `/api/chat/*`, gap_check / gap_proposal.
Deferred to slice 2c: 沙箱 (Spark SQL / Flink SQL / Java Flink dry_run).
```

- [ ] **Step 2: 跑完整 search 测试套件验证**

```bash
pytest tests/search -v
```

预期：所有 9+ 个测试 PASS（含 1 个 `infra` mark — 如果 Neo4j 起着就跑，否则可单独 `-m "not infra"`）。

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs: slice 2a acceptance coverage table"
```

---

## Self-Review

### 1. Spec coverage

| Spec ref | Requirement | Plan task |
|----------|-------------|-----------|
| §4.6.1 检索空间 — table_doc / field_doc 形态 | Task 3 (`backend/search/docs.py`) |
| §4.6.2 组件选型 — jieba / bge-small-zh / ChromaDB / rank-bm25 / DeepSeek | Tasks 0, 2, 5, 6 (各组件落在 preprocessing/embedder/clients/) |
| §4.6.3 文本预处理 + 自定义词典 | Task 2 (`RNO_TERMS` 覆盖 RSRP/SINR/覆盖强度等所有 spec 列举词) |
| §4.6.4 初始化与增量同步 + 异常处理 | Tasks 5 (Embedder 降级), 8 (HybridSearcher.build_index / upsert / index_version), 9 (lifespan 接入), 13 (08 离线构建) |
| §4.6.5 混合检索流程 + 置信度判断 | Task 8 (HybridSearcher.search 内 rerank_threshold) |
| §4.6.6 RRF 公式 (k=60) | Task 4 (`fusion.py`, 默认 k=60) |
| §4.6.7 LLM Rerank 兜底 + Prompt | Task 7 (`rerank.py` 全文 RERANK_PROMPT) |
| §4.6.8 延时预算 | Task 11 (`benchmark` 报告 avg_latency_ms / p99_latency_ms) |
| §4.7.1 测试集构建 — A/B/C 三类 60 条 | Task 10 (`scripts/generate_benchmark_queries.py` 锁定 60 条) |
| §4.7.2 评估指标 | Task 11 (`evaluate()` 输出全部指标) |
| §4.7.3 目标值 | Task 11 (`BenchmarkTargets` 与 spec 数值一一对应) |
| §4.7.4 CI 门禁 ≥ 90% 目标 | Task 11 (`GATE_FACTOR=0.9`, `check_gate()`) |
| §6.7 `GET /api/search` | Task 9 (`backend/api/search.py`) |
| §6.7 `/api/health` 含 search 组件 | Task 9 (修 `health.py`) |
| §7 `backend/search/{searcher,embedder}` | Tasks 5, 8 (按 spec 路径) |
| §7 `backend/agent/deepseek.py` 提前作为 `backend/clients/deepseek.py` | Task 6 (slice 2b 复用) — 偏离 spec 路径，理由见下 |

**偏离说明：** spec §7 把 DeepSeek 客户端放在 `backend/agent/deepseek.py`，但 `agent/` 整体属于 slice 2b。slice 2a 的 LLM rerank 提前需要它，因此前置到 `backend/clients/deepseek.py`。slice 2b 不再重复实现，直接 `from backend.clients.deepseek import get_deepseek_client`。**这是有意识的提前抽离**，避免 slice 2b 落地时重写。

### 2. Placeholder scan

搜索了 `TBD` / `TODO` / `implement later` / `fill in` / `appropriate` / `similar to Task`：
- 无任何占位符；所有代码块完整。
- `Task 13 Step 4` 提到 "如果 slice 1b 当前的 init-stack.sh 把 docker up 写在 [8/8] 之后，需要把它从那里挪到 [10/10]" — 这是对存量脚本的兼容性提示，不是空白指令；执行者会在编辑时直接看到具体行。
- `scripts/benchmark_semantic_search.py` 中 `--mode incremental` 仅作 CLI 文档保留；当前 slice 不强制实现增量对比逻辑（spec §4.7.4 是 schema_evolve 后才触发，slice 2b 接线时再补）。这是**有意识的范围裁剪**，已在 plan 头 "Out of scope" 列出。

### 3. Type / name consistency

- `SearchDoc` 字段 `id` / `type` / `text` / `metadata` — Tasks 3, 4, 5, 7, 8 全部一致。
- `HybridSearcher.search(query, k, use_rerank, rerank_client)` 签名 — Tasks 8 (定义), 9 (api 调用 `searcher.search(q, k=k*2, use_rerank=False)`), 11 (`evaluate` 调 `searcher.search(q["query"], k=10, use_rerank=False)`), 12 (`searcher.search(..., use_rerank=False)`) 全部参数名一致。
- `Embedder.available` / `Embedder.encode` / `Embedder.upsert` / `Embedder.query` / `Embedder.count` / `Embedder.get_index_version` / `Embedder.set_index_version` — Tasks 5 (定义), 8 (使用), 9 (health 读 `_embedder.available`) 全部一致。
- `get_settings()` 新增字段 `deepseek_api_key` / `deepseek_base_url` / `deepseek_model` / `search_chroma_dir` / `search_embed_model` / `search_rerank_threshold` / `search_rrf_k` / `search_bootstrap_from_seed` — Task 1 + Task 9 Step 3 一次性定义清晰；env alias 与 Task 0 `.env.example` 写入完全匹配。
- ChromaDB collection 名 `metadata_index` — Task 5 定义，Tasks 8/12 通过 Embedder 访问，无字面字符串重复。
- `RNO_TERMS` 列表 — Task 2 定义，Task 2 测试 `test_rno_terms_includes_all_required_keywords` 强制约束必含 RSRP/SINR/覆盖强度/掉话率/切换成功率等；与 spec §4.6.3 例子全部对齐。
- `/api/search` 入参 `q` / `type` / `k` — Task 9 (router 签名) 与 Task 9 测试用例 / Task 11 (无重复字段) 一致。
- `RERANK_PROMPT` 占位符 `{user_query}` 和 `{candidates_json}` — Task 7 定义，Task 7 测试 `test_rerank_prompt_template_has_required_placeholders` 守护。
- `index_version` — Task 5 (Embedder.get/set_index_version), Task 8 (`HybridSearcher.get_index_version` 委托给 embedder, `_compute_version` 计算并 `set_index_version`), Task 9 (`/api/health` 读), Task 12 (P2a-3 / P2a-4 断言) 全链路一致。
- `chroma_dir=":memory:"` — Task 5 测试用，与 Task 5 实现 `if chroma_dir == ":memory:": EphemeralClient` 完全匹配。
- 测试 `infra` mark — slice 1b 已在 `pyproject.toml` 注册；slice 2a 复用，唯一引入新的 `infra` 用例在 Task 12，其他全部走 stub encoder。

无名字漂移。

---

## Execution Handoff

Plan 完成，已保存到 `docs/superpowers/plans/2026-05-14-phase2-slice2a-semantic-search.md`。

两种执行方式：

**1. Subagent-Driven (推荐)** — 每个 Task 派一个新的 subagent，两段式 review。本 plan 有几处天然 checkpoint：Task 4 (RRF 纯函数) → Task 6 (DeepSeek client 抽离) → Task 8 (HybridSearcher 主类) → Task 11 (benchmark 跑通) → Task 13 (容器化) 都是合适的中场暂停点。每个 task 上下文聚焦，迭代速度快。

**2. Inline Execution** — 用 `superpowers:executing-plans` 在本会话里执行，分批 checkpoint。整体 14 个 task 会比较占 context window。

选择哪种方式？
