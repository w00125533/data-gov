# 08. 实施路线

## Phase 0: 文档统一

目标：

- 生成统一文档集。
- 归档旧入口文档和旧 6 月子文档。
- 明确 Spring Boot、GaussDB、shared infra、`/rest/...`、X6 和完整 UI 范围。

退出标准：

- 新文档集成为唯一入口。
- 历史文档可追溯。
- 冲突口径在迁移附录和决策文档中可查。

## Phase 1: 治理核心收敛

目标：

- Spring Boot governance-server 成为治理主服务。
- GaussDB 成为元数据主库。
- `/rest/oss/inner/modelengineservice/v1` 覆盖 metadata、lineage、subscription、query、event、drift。

退出标准：

- Contract tests 覆盖主要 API。
- Docker runtime 可启动。
- 前端通过代理访问正式 API。

## Phase 2: 旧能力迁移

目标：

- FastAPI 元数据、血缘和旧 `/api` 能力迁移到 Spring Boot。
- Neo4j 元数据切换到 GaussDB。
- Python 服务保留 Agent、搜索和沙箱边界。

退出标准：

- 新增治理能力不再依赖 Neo4j。
- 前端治理页面默认使用 `/rest/...`。
- 旧 API 有兼容或下线策略。

## Phase 3: UI 基础闭环

目标：

- `/metadata`、`/metadata/lineage`、`/pipeline`、`/schema-evolution` 接入正式 API。
- 用户能看到主要治理功能。

退出标准：

- 可视化 E2E 覆盖 metadata、lineage、pipeline、schema evolution。
- 真实 Docker E2E 覆盖元数据注册和血缘展示。

## Phase 4: X6 画布迁移

目标：

- 血缘图迁移到 X6。
- Pipeline DAG 迁移到 X6。
- 字段端口、复杂边路由、边详情、mini map、缩放和拖拽稳定。

退出标准：

- X6 血缘图能展示字段级边。
- X6 Pipeline 能展示正向和反向链路。
- 可视化验收覆盖节点选择、边选择、缩放和详情同步。

## Phase 5: Agent 全链路

目标：

- metadata / lineage / pipeline 跳转 Chat。
- Chat 支持上下文注入、代码生成、dry-run、preview、gap 补齐和 schema/lineage 更新。

退出标准：

- 至少一个正向 ETL 链路可从 UI 发起并完成 dry-run。
- 至少一个元数据演进链路可通过 UI 预览 diff 并提交治理 API。

## Phase 6: 治理后台增强

目标：

- UI 展示订阅、通知、drift、查询记录和 SDK 注册状态。

退出标准：

- 可在 UI 查看某 metadata 的订阅和查询事实。
- 可在 UI 查看 drift 记录和通知状态。

## Phase 7: 高级维护交互

目标：

- X6 右键菜单。
- 拖拽建边。
- Monaco 表达式编辑。
- 字段删除影响分析。
- YAML diff。

退出标准：

- 维护操作通过 Spring Boot API 写入。
- 失败时 UI 给出可恢复错误。
- 相关操作有 Playwright 可视化验收。
