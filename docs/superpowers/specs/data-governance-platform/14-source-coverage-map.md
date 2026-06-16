# 14 来源覆盖映射

## 1. 5 月文档覆盖

来源：5 月无线 RNO 语义化服务设计。归档文件已删除，本表保留覆盖映射。

| 来源 | 新落点 | 说明 |
| --- | --- | --- |
| 功能树全景 | 01-08 | 按一级功能点编号拆分，二级功能点保留固定模板。 |
| RNO 分层和 10 表 | 09 | 保留分层、表、核心字段、上游依赖。 |
| Neo4j Schema | 10 | 作为默认图数据库模型保留。 |
| YAML 副本 | 02、09 | 保留导出、预览和 diff。 |
| Agent LangGraph | 04 | 保留 classifier、forward_etl、reverse_synth、schema_evolve 等能力。 |
| Agent State/Tools | 04、11 | 保留状态和内部 API。 |
| DeepSeek | 04、12 | 保留为 Agent 能力。 |
| 语义检索 Benchmark | 09、13 | 保留指标和样例。 |
| 沙箱 | 07、11、13 | 保留模板、提交、HDFS 回读、自动重试和清理。 |
| Web UI | 02-06 | 保留 metadata、lineage、chat、pipeline、schema-evolution。 |
| Health | 01 | 保留 `/health`。 |
| E2E 验收 | 13 | 保留并按新口径改写。 |

## 2. 6 月文档覆盖

来源：6 月数据产品治理设计及 data-governance 拆分文档。归档文件已删除，本表保留覆盖映射。

| 来源 | 新落点 | 说明 |
| --- | --- | --- |
| Spring Boot 治理主服务 | 00、01、11 | 保留为正式治理 API 服务。 |
| GaussDB 数据模型 | 10 | 改为兼容持久化模型。 |
| API 前缀 | 11 | 保留 `/rest/oss/inner/modelengineservice/v1`。 |
| `/metadata/register` 启动快照 | 11、13 | 保留。 |
| PATCH/DELETE 运行时语义 | 02、11 | 保留。 |
| metadata list/detail/lineage | 02、03、11 | 保留。 |
| API query / SQL Gateway | 08、11 | 保留。 |
| subscription API | 08、11 | 保留。 |
| Java SDK / Kafka listener | 08、13 | 保留。 |
| runtime 时序 | 01、08 | 保留并拆入功能点。 |
| drift | 08、13 | 保留并扩展。 |
| shared infra | 01 | 保留。 |

## 3. 本轮新增要求覆盖

| 要求 | 新落点 | 状态 |
| --- | --- | --- |
| 默认图数据库，同时支持 GaussDB | 00、10 | 已覆盖。 |
| 按一级功能拆分子文档 | 01-08 | 已覆盖。 |
| 二级功能固定章节模板 | 01-08 | 已覆盖。 |
| 子文档编号 | 00-14 | 已覆盖。 |
| Agent API 是否定义 | 04、11 | 已作为平台内部 API 定义。 |
| 沙箱 API 是否定义 | 07、11 | 已作为平台内部 API 定义。 |
