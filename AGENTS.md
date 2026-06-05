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

## 公共基础设施约束

- 当前整改边界：`data-gov` 本地只保留 Neo4j、backend/frontend 和必要的 Spark 工具容器；HDFS/YARN、Hive Metastore/HMS Postgres、Kafka 和 StarRocks 由 `../shared-data-infra` 提供，通过 `shared-data-infra` external network 访问。
- 在新增或修改 Docker Compose 基础设施前，先检查同级目录下其他工程以及计划中的公共基础设施是否已经提供相同能力，尤其是 HDFS、Hive Metastore、HiveServer2、Spark、YARN、Kafka、ZooKeeper、StarRocks、Prometheus、Grafana 等。
- 能复用公共基础设施时，不要在本工程再次新增一套同类服务；业务容器应通过 external network、环境变量和独立命名空间连接公共服务。
- 本工程需要隔离时，优先使用独立 HDFS 路径、Hive database、Kafka topic prefix、StarRocks database、checkpoint 路径和数据卷，而不是复制基础设施容器。
- 只有当测试、性能对比或故障隔离明确要求独占实例时，才允许在本工程保留 project-local 基础设施，并在相关 compose 或文档中写明原因。
- 避免新增固定 `container_name` 和固定宿主端口，除非该服务是公共入口或已有约定；新增端口前要确认不会与其他工程冲突。
- 修改基础设施后，更新 README/AGENTS 中的启动说明，并运行对应 `docker compose ... config` 验证配置有效。

## 协作注意

- 修改 API 时同步查看对应测试。
- 修改元数据时关注 Neo4j、`metadata-yaml/` 和 YAML 同步逻辑。
- 修改搜索时覆盖 BM25 降级、向量检索、融合和 rerank。
- 修改沙箱时区分 mock 单元测试与真实 infra 测试。
- 文档请保持 UTF-8，避免扩大无关改动。
