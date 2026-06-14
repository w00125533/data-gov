# 20. 来源覆盖映射

本文用于检视新文档集是否覆盖 2026-05-13 和 2026-06-10 两组历史文档的信息。它不是新的需求来源，而是追踪表：每个历史章节在新文档中的落点、保留方式和目标态修订。

## 1. 覆盖原则

- 5 月文档提供产品愿景、完整 UI 范围、RNO 样例域、Agent、搜索、沙箱、项目结构和 Phase 验收细节。
- 6 月文档提供 Spring Boot、GaussDB、正式 API、订阅、查询、通知、drift、SDK 和运行时细节。
- 两者冲突时，以用户确认后的目标口径为准：Spring Boot、GaussDB、shared infra、`/rest/oss/inner/modelengineservice/v1`、X6。
- 历史实现不在正文目标态重复作为目标，只在迁移附录和覆盖表中说明。

## 2. 5 月文档覆盖映射

| 5 月章节 | 原内容 | 新文档落点 | 修订口径 |
| --- | --- | --- | --- |
| 1. 概述 | 语义化元数据管理、数据加工逻辑生成、反向样例生成。 | `01-product-scope.md`, `02-capability-map.md` | 平台名称改为数据治理平台，RNO 为样例域。 |
| 核心能力 | NL-to-Code、正向 ETL、反向合成、元数据演进、Web 可视化。 | `01`, `13`, `14`, `17` | 全部保留，Agent 写入主库改为通过 Spring Boot API。 |
| 范围 | Phase 1 基础设施、Phase 2 Agent、Phase 3 UI。 | `08-implementation-roadmap.md`, `16-e2e-acceptance-detailed-spec.md` | 扩展为 Phase 0 到 Phase 7。 |
| 技术决策总表 | FastAPI、Neo4j、LangGraph、DeepSeek、G6、Docker 栈。 | `03`, `10`, `11`, `13`, `14` | FastAPI/Neo4j/G6 改为历史迁移来源，目标为 Spring Boot/GaussDB/X6。 |
| 功能树全景 | 1 到 8 大类完整功能树。 | `17-feature-matrix-detailed.md` | 逐项映射状态、目标态和验收。 |
| 2.1 分层结构 | ODS、DWD、DWS、ADS、EVAL。 | `12-rno-domain-and-metadata-detailed-spec.md` | 完整保留，并说明 layer 在目标模型中的存储方式。 |
| 2.2 10 张样例表 | RNO 10 张表、核心字段、上游依赖。 | `12` | 完整保留并扩展字段级定义。 |
| 2.3 Neo4j Schema | Table、Field、Change、HAS_FIELD、DERIVES_FROM。 | `04-data-model.md`, `10-migration-appendix.md`, `12` | 作为迁移来源映射到 GaussDB。 |
| 2.4 元数据演进策略 | NL 驱动变更、一致性校验、version、YAML git diff。 | `12`, `13`, `14`, `15` | 写入从 Neo4j 改为 Spring Boot API + GaussDB。 |
| 2.5 YAML 元数据副本 | metadata-yaml 目录和 YAML 示例。 | `12`, `14`, `19` | 保留 YAML 人工审阅和 diff，主存储改为 GaussDB。 |
| 3. Docker 一体化验证栈 | base-compose、app-compose、FastAPI、存储流向、初始化。 | `06-runtime-and-infra.md`, `19-project-structure-and-infra-detailed.md` | base-compose 改为 shared infra profile。 |
| 3.6 健康检查面板 | 各组件状态卡片。 | `07-ui-target-design.md`, `14`, `19` | 保留并扩展到 Spring Boot、Agent、GaussDB、shared infra。 |
| 4. NL-to-Code Agent | LangGraph StateGraph、节点、State、Tools、DeepSeek、重试。 | `13-agent-search-sandbox-detailed-spec.md` | 保留节点职责，工具写入改为调用 Spring Boot。 |
| 4.6 语义检索 | 表级/字段级文档、BM25、dense、RRF、rerank、增量同步。 | `13` | 保留，并把元数据来源改为 Spring Boot API。 |
| 4.7 Benchmark | 测试集、指标、目标值、CI 门禁。 | `13` | 保留核心指标。 |
| 5. 沙箱 | 统一模型、模板、提交方式、控制器、资源限制。 | `13`, `16` | 保留并明确 shared infra YARN。 |
| 6.1 UI 技术栈 | React、Ant Design、G6。 | `07`, `14` | React/Ant Design 保留，G6 改为 X6 目标态。 |
| 6.2 页面路由 | metadata、lineage、chat、pipeline、schema evolution、health。 | `07`, `14`, `17` | 全部保留。 |
| 6.3 元数据管理界面 | 页面布局、功能详单、新建编辑表、字段抽屉。 | `14`, `17` | 保留，并改为调用正式 API。 |
| 6.4 血缘图界面 | 页面布局、交互清单。 | `14` | 用 X6 重写节点、端口、边、工具栏和空态。 |
| 6.5 血缘图维护 | 右键菜单、拖拽建边、Chat context。 | `14`, `17` | 完整保留，目标态用 X6。 |
| 6.6 对话面板 | 布局、对话功能、代码卡、dry-run。 | `13`, `14`, `17` | 保留，并增加结构化 cards。 |
| 6.7 API 端点 | 旧 FastAPI 端点。 | `10-migration-appendix.md`, `15` | 旧端点作为迁移来源，正式端点使用 `/rest`。 |
| 6.8 Pipeline 可视化 | 页面布局、正向、反向、Chat 联动。 | `14`, `17` | 保留，目标态用 X6。 |
| 6.9 Schema Evolution | 时间线、diff、YAML diff、版本 commit 映射。 | `14`, `16`, `17` | 保留，事件来源改为 GaussDB metadata_event。 |
| 7. 项目结构 | 目录树、backend、frontend、templates、metadata-yaml。 | `19` | 保留并加入 Spring Boot 多模块。 |
| 8. E2E 验收用例 | Phase 1/2/3 验收表。 | `16` | 保留并扩展到 Phase 0 到 Phase 7。 |
| 9. 非功能要求 | 安全、调试、清理、文档。 | `06`, `09`, `19` | 保留在运行时、发布门禁和项目结构中。 |

## 3. 6 月入口文档覆盖映射

| 6 月入口章节 | 原内容 | 新文档落点 | 修订口径 |
| --- | --- | --- | --- |
| 背景与目标 | 数据注册、发现、订阅、消费、查询、血缘。 | `01`, `02`, `15` | 完整保留为治理主线。 |
| 文档集导航 | API、数据模型、运行时、架构视图、决策。 | `index.md` | 新文档集扩展为 20 个文件。 |
| 当前核心设计 | API 前缀、metadata、metadataId、assetCode、GaussDB、StarRocks。 | `03`, `05`, `15` | 完整保留。 |
| 实施阶段 | Spring Boot、注册发现、SDK、查询、事件 drift。 | `08`, `16` | 融合 UI 和 Agent 后扩展。 |
| 验收标准 | SDK 快照、metadata 查询、查询、通知、drift。 | `09`, `16` | 扩展为 Contract、Runtime、UI、Real E2E。 |
| 基础设施约束 | shared infra 复用。 | `06`, `19` | 保留并作为硬约束。 |

## 4. 6 月 API 文档覆盖映射

| API 文档章节 | 新文档落点 | 保留程度 |
| --- | --- | --- |
| API 分类总览 | `05`, `15` | 保留并扩展。 |
| 接口概览表 | `05`, `15`, `18` | 保留完整路径和资源。 |
| POST `/metadata/register` | `15`, `18` | 保留请求/响应结构、快照语义和校验。 |
| PATCH `/metadata/{metadataId}` | `15`, `18` | 保留运行时修改语义。 |
| DELETE `/metadata/{metadataId}` | `15`, `18` | 保留注销语义。 |
| GET `/metadata` | `15`, `18` | 保留过滤、分页和响应字段。 |
| GET `/metadata/{metadataId}` | `15`, `18` | 保留 schema、binding、qualifiedName。 |
| GET `/metadata/{metadataId}/lineage` | `15`, `18` | 保留 nodes、edges、fieldEdges。 |
| POST `/apiquery/{metadataId}` | `15`, `18` | 保留查询 DSL、订阅 header、query_record。 |
| POST `/sqlquery` | `15`, `18` | 保留只读 SQL、参数、rewrittenSql。 |
| Subscriptions | `15`, `18` | 保留创建、查询、取消、notifyOn。 |
| SDK 快速组装 | `15`, `19` | 保留 Builder 示例、物理表检查、listener。 |

## 5. 6 月数据模型覆盖映射

| 表 | 新文档落点 | 保留程度 |
| --- | --- | --- |
| `metadata` | `04`, `15` | 保留字段、状态、作用域和唯一约束。 |
| `metadata_field` | `04`, `15` | 保留字段 schema 和唯一约束。 |
| `metadata_binding` | `04`, `15` | 保留 binding 字段和 qualifiedName。 |
| `lineage_edge` | `04`, `12`, `15` | 保留表级/字段级统一边。 |
| `consumer` | `04`, `15` | 保留消费方模型。 |
| `subscription` | `04`, `15`, `18` | 保留声明态和通知关注。 |
| `query_record` | `04`, `15` | 保留运行态事实。 |
| `consumer_job` | `04`, `15` | 保留作业声明。 |
| `metadata_event` | `04`, `15` | 保留事件模型。 |
| `subscription_notification` | `04`, `15` | 保留通知发送状态。 |
| `drift_record` | `04`, `15` | 保留 drift 类型和状态。 |

## 6. 6 月运行时覆盖映射

| 运行时章节 | 新文档落点 | 保留程度 |
| --- | --- | --- |
| 核心原则 | `06`, `15` | 保留启动态和运行态区分。 |
| 启动快照同步 | `06`, `15`, `16` | 保留完整流程和幂等规则。 |
| 启动快照幂等性 | `15`, `16` | 保留幂等键和声明 hash。 |
| 运行时动态修改 | `06`, `15` | 保留 PATCH 语义。 |
| 运行时动态取消注册 | `06`, `15` | 保留 DELETE 软下线。 |
| 订阅运行时 | `15`, `18` | 保留 metadataId 单对象订阅。 |
| 查询运行时 | `15` | 保留 query_record 事实。 |
| 通知运行时 | `06`, `15`, `19` | 保留 Kafka 异步通知。 |
| Drift 运行时 | `15`, `16` | 保留三类 drift。 |
| 运行时序 | `15` | 保留 Mermaid 时序并扩展。 |

## 7. 6 月架构决策覆盖映射

| 决策 | 新文档落点 | 状态 |
| --- | --- | --- |
| Java Spring Boot 主服务 | `03`, `11` | 已确认。 |
| GaussDB 主库 | `03`, `04`, `11` | 已确认。 |
| `/rest` API 前缀 | `05`, `11`, `18` | 已确认。 |
| `metadata` 资源命名 | `05`, `15` | 已确认。 |
| 启动快照复用注册接口 | `06`, `15` | 已确认。 |
| PATCH/DELETE 只用于运行时 | `06`, `15` | 已确认。 |
| StarRocks 查询入口 | `06`, `15` | 已确认。 |
| 产品 API 优先 | `15` | 已确认。 |
| Kafka 不进入统一查询 | `05`, `15` | 已确认。 |
| 订阅是使用意图 | `15` | 已确认。 |
| 第一阶段 Java SDK | `15` | 已确认。 |
| 简化关系模型 | `04`, `15` | 已确认。 |
| 查询事实和作业声明分离 | `15` | 已确认。 |
| Kafka 异步通知 | `06`, `15` | 已确认。 |

## 8. 明确没有按原样保留的内容

以下内容没有作为目标态原样保留，但已保留迁移说明：

| 历史内容 | 不原样保留原因 | 新目标 |
| --- | --- | --- |
| FastAPI 作为主后端 | 用户确认治理 API 尽量使用 Spring Boot。 | Spring Boot 主服务，Python 只保留 Agent/搜索/沙箱。 |
| Neo4j 作为元数据主库 | 用户确认元数据以 GaussDB 为准。 | GaussDB 表模型和服务端图查询。 |
| 本工程 base-compose 基础设施 | AGENTS 和用户确认复用 shared infra。 | `../shared-data-infra`。 |
| G6 作为目标图引擎 | 用户确认目标态图画布全部用 X6。 | X6 血缘图和 Pipeline DAG。 |
| 旧 `/api` 作为正式接口 | 用户确认采用 6 月 `/rest` 前缀。 | `/rest/oss/inner/modelengineservice/v1`。 |

## 9. 后续检视方法

检视新文档时建议按这个顺序：

1. 先看 `index.md` 和 `11-open-decisions.md`，确认目标口径。
2. 看 `17-feature-matrix-detailed.md`，确认 5 月功能树没有被删。
3. 看 `12`、`13`、`14`，确认 RNO、Agent、UI 细节。
4. 看 `15`、`18`，确认 6 月 API 和 SDK 细节。
5. 看 `16`，确认验收用例是否覆盖目标态。
6. 看 `20`，逐节对照历史文档。
