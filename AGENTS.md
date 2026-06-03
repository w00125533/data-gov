# AGENTS.md

## 项目简介

`data-gov` 是无线 RNO 数据治理语义服务 PoC，提供元数据管理、血缘查询、中文语义搜索、Agent 辅助开发和 Spark/Flink 沙箱 dry-run。

## 技术栈

- Python 3.11+，FastAPI，Uvicorn。
- 配置：`pydantic-settings`，入口配置见 `backend/config.py`。
- 数据与中间件：Neo4j 5 + APOC、Postgres、HDFS/YARN、Hive Metastore、Kafka、StarRocks。
- 搜索：`sentence-transformers`、Chroma、BM25、`jieba`、RRF，默认模型 `BAAI/bge-small-zh-v1.5`。
- Agent/LLM：LangGraph、LangChain、DeepSeek API、SSE 流式聊天。
- 沙箱：Java 17、Maven、Spark 3.5.4、Flink 1.19.1、Hadoop 3.3.6。
- 测试：pytest；`infra` marker 表示需要 Docker 基础设施。

## 项目结构

- `backend/`：后端 Python 包。
- `backend/main.py`：FastAPI 应用入口，注册 API 并初始化 Neo4j、搜索索引和聊天会话。
- `backend/api/`：health、metadata、search、schema、chat 路由。
- `backend/metadata/`：元数据模型、服务层和 Neo4j 图谱访问。
- `backend/search/`：语义搜索、BM25、向量索引、融合和 rerank。
- `backend/agent/`：LangGraph Agent、状态、工具、提示词、聊天和 YAML 同步。
- `backend/agent/nodes/`：Agent 节点实现。
- `backend/sandbox/`：Spark/Flink/Hadoop 沙箱编译、提交、重试和错误解析。
- `metadata-yaml/`：分层元数据 YAML。
- `templates/`：Spark SQL、Flink SQL、Java Flink 沙箱模板。
- `docker/`：Hadoop、Hive、Spark、Flink 等配置。
- `init-scripts/`：基础设施初始化、样例数据、Neo4j seed、YAML 导出、搜索索引构建。
- `scripts/`：栈初始化、健康检查等待、benchmark 脚本。
- `tests/`：pytest 测试，按 `api`、`infra`、`search`、`agent`、`sandbox` 分组。
- `base-compose.yml`：基础数据平台服务。
- `app-compose.yml`：后端应用容器。
- `pyproject.toml`：依赖、打包和 pytest 配置。

## 常用命令

```bash
cp .env.example .env
docker compose -f base-compose.yml up -d
./scripts/init-stack.sh
python -m pip install -e ".[dev]"
python -m pytest -m "not infra"
python -m pytest -m infra
```

## 协作注意

- 修改 API 时同步查看对应测试。
- 修改元数据时关注 Neo4j、`metadata-yaml/` 和 YAML 同步逻辑。
- 修改搜索时覆盖 BM25 降级、向量检索、融合和 rerank。
- 修改沙箱时区分 mock 单元测试与真实 infra 测试。
- 文档请保持 UTF-8，避免扩大无关改动。
