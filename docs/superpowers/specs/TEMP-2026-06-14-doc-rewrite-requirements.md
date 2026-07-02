# 临时文档：统一规格文档重写要求

> 2026-06-14 | 临时记录 | 用于后续重新设计和生成统一文档前的需求输入

## 1. 背景

当前存在两组历史规格文档：

- `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md`
- `docs/superpowers/specs/2026-06-10-data-product-governance-design.md`
- `docs/superpowers/specs/data-governance/`

5 月文档是第一版，信息量大、细节完整，覆盖无线 RNO 样例域、元数据、Agent、沙箱、Web UI、项目结构和验收用例。

6 月文档是在 5 月基础上的演进，重点补充 Spring Boot 治理主服务、GaussDB 主库、正式 API、订阅、统一查询、通知、drift、SDK 和运行时设计。

之前生成的统一文档过度摘要化，丢失了大量 5 月和 6 月文档中的具体信息。后续重写必须以“保留信息量”为优先目标，不能只做高层抽象。

## 2. 文档重写总原则

1. 新文档可以采用“总文档 + 子文档”的形式组织，但不能压缩掉原始细节。
2. 5 月文档约 111KB，6 月文档集约 80KB；新文档的信息量应接近两者融合后的规格级内容，而不是几十 KB 的摘要。
3. 允许重组、去重、修正冲突，但必须保留具体功能树、样例表、字段、API 参数、UI 交互、Agent 节点、沙箱、验收步骤等细节。
4. 需要有来源覆盖映射，说明 5 月和 6 月每个主要章节在新文档中的落点。
5. 如果存在冲突，应明确标注冲突、采用目标口径，并在需要时让用户确认。

## 3. 已确认目标口径

### 3.1 治理主服务

尽量采用 Spring Boot API 形式。

FastAPI 之前主要是为了方便 Python Agent 实现。目标态中：

- Spring Boot 是治理主服务。
- Spring Boot 承载正式治理 API。
- Python/FastAPI 只保留 Agent、语义搜索、LLM、沙箱编排等 Python 生态能力。
- Python 服务不直接作为元数据主写入口。

### 3.2 元数据主库

元数据以 GaussDB 为准。

目标态中：

- 元数据、字段、物理绑定、血缘、订阅、查询记录、事件、通知、drift 主库存储在 GaussDB。
- 原 Neo4j 元数据能力全部切换到 GaussDB。
- Neo4j 只能作为历史实现或迁移来源，不再作为目标态元数据主库。

### 3.3 基础设施

基础设施改为复用 `../shared-data-infra`。

目标态中：

- 本工程不重复定义 HDFS、Hive、Spark、YARN、Kafka、ZooKeeper、StarRocks、Prometheus、Grafana、GaussDB、Neo4j 等共享基础设施。
- 本工程只保留 backend、frontend、governance-server、Chroma 和应用级资源。
- 修改基础设施后必须执行 compose config 校验。

### 3.4 API 前缀

正式 API 采用 6 月文档中的前缀：

```text
/rest/oss/inner/modelengineservice/v1
```

说明：

- 用户曾输入过 `modelingineservice`，已确认按现有 6 月文档和代码中的 `modelengineservice`。
- 旧 `/api/...` 仅作为 legacy 或迁移来源，不作为正式治理 API 目标。

### 3.5 UI 范围


注意：

- 目录结构可以调整。
- 关键是不能只保留摘要。
- 每个子文档都要有足够细节支撑后续实施计划。

## 5. 旧文档处理偏好

之前讨论时曾选择“归档旧文档”，但本次已回退，不再执行归档。

后续如果再次生成统一文档，应先确认：

1. 是否保留原文件不动，只新增新文档集。
2. 是否在新文档确认后再移动旧文档到 archive。
3. 是否在旧文档顶部加历史说明。

在新文档质量未确认前，不应再次直接移动或删除旧文档。

## 6. 后续重写前必须补充的内容

新文档至少应覆盖以下具体信息：

### 6.1 来自 5 月文档

- 完整功能树。
- RNO 分层结构。
- 10 张样例表。
- 样例字段和字段级血缘。
- YAML 元数据副本格式。
- 元数据演进策略。
- Agent LangGraph 节点。
- Agent State。
- Agent Tools。
- DeepSeek 集成。
- 自动重试。
- 语义检索技术实现。
- Benchmark 测试集、指标和目标值。
- 沙箱统一模型、模板、提交方式、资源限制。
- Web UI 页面布局和功能详单。
- 血缘图维护、右键菜单、拖拽建边。
- Chat 面板、代码卡片、dry-run、gap 补齐。
- Pipeline 正向/反向可视化。
- Schema Evolution timeline、diff、YAML diff。
- 项目结构。
- Phase 1/2/3 E2E 验收用例。
- 非功能要求。

### 6.2 来自 6 月文档

- Spring Boot 治理主服务。
- GaussDB 数据模型。
- API 分类和完整接口。
- `/metadata/register` 启动快照语义。
- PATCH / DELETE 运行时语义。
- metadata 列表、详情、lineage API。
- API query。
- SQL Gateway。
- subscription API。
- SDK Builder 示例。
- StarRocks / Iceberg 物理表检查和自动建表。
- Kafka notification listener。
- 启动同步运行时序。
- 查询审计运行时序。
- 元数据事件通知运行时序。
- Drift 分析规则。
- 架构决策与权衡。
- shared infra 部署约束。

## 7. 质量要求

后续重写完成后，应至少自检：

1. 新文档总信息量不能明显低于历史文档融合后的规格级信息量。
2. 不能只写抽象目标，必须包含具体表、字段、参数、交互、命令和验收步骤。
3. API 前缀不能误写。
4. 目标态不能再写 Neo4j 为主库。
5. 目标态不能再写 G6 为图画布。
6. 目标态不能把 5 月 UI 范围删减掉。
7. 必须有来源覆盖表，方便逐节检查。
8. 必须先让用户检视，再进入实施计划。

## 8. 当前回退状态说明

本临时文档生成前，已通过 `git revert` 回退两次文档合并相关提交：

- `e9418fa Expand unified governance platform specification`
- `26136cd Document unified data governance platform design`

因此，原 5 月和 6 月文档已恢复到合并前路径。本文档仅用于记录本轮新要求，不代表最终统一文档。
