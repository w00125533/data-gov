# 数据治理平台设计文档集

> 2026-06-14 | Status: Draft for review

本文档集是 `data-gov` 后续需求、设计、实施计划和验收的唯一主入口。它融合并取代两组历史设计：

- `../archive/2026-05-13-wireless-rno-data-service-design.md`
- `../archive/2026-06-10-data-product-governance-design.md`
- `../archive/data-governance-2026-06-10/`

## 1. 权威口径

- 平台定位为通用数据治理平台；无线 RNO 是样例业务域、默认数据集和验收场景。
- 治理主服务采用 Java Spring Boot，正式接口统一使用 `/rest/oss/inner/modelengineservice/v1`。
- 元数据、字段、物理绑定、血缘、订阅、查询记录、事件、通知和 drift 以 GaussDB 为主库。
- 原 Neo4j 元数据模型退出目标态，作为历史实现迁移来源保留在附录。
- Python 服务保留 Agent、语义搜索、沙箱编排、LLM 调用等 Python 生态能力，不作为元数据主写入口。
- 基础设施复用 `../shared-data-infra`；本工程只保留应用服务、前端、Chroma 和应用级数据卷。
- UI 目标范围完整继承 2026-05-13 版本，包括 metadata、lineage、chat、pipeline、schema evolution、sandbox/preview 和 health。
- 目标态所有交互式图画布统一使用 AntV X6；当前 G6 实现作为过渡实现迁移。

## 2. 文档导航

| 文档 | 内容 |
| --- | --- |
| [01-product-scope.md](01-product-scope.md) | 平台目标、业务样例、完整能力范围。 |
| [02-capability-map.md](02-capability-map.md) | 元数据、血缘、Agent、Pipeline、订阅、查询、通知、drift、沙箱和健康检查能力地图。 |
| [03-architecture.md](03-architecture.md) | Spring Boot、GaussDB、Python Agent、Frontend、Java SDK 和 shared infra 的目标架构。 |
| [04-data-model.md](04-data-model.md) | 以 GaussDB 为准的核心数据模型。 |
| [05-api-contracts.md](05-api-contracts.md) | 正式 API 前缀、资源、请求语义和错误口径。 |
| [06-runtime-and-infra.md](06-runtime-and-infra.md) | 启动快照、运行时修改、通知、查询、Docker 和基础设施复用。 |
| [07-ui-target-design.md](07-ui-target-design.md) | 以 2026-05-13 UI 范围为准的目标态页面和交互。 |
| [08-implementation-roadmap.md](08-implementation-roadmap.md) | 分阶段实施路线、当前状态和退出标准。 |
| [09-acceptance-suite.md](09-acceptance-suite.md) | API、Docker、UI、真实端到端验收用例集。 |
| [10-migration-appendix.md](10-migration-appendix.md) | FastAPI、Neo4j、旧 `/api`、G6 和旧 compose 的迁移策略。 |
| [11-open-decisions.md](11-open-decisions.md) | 已确认决策和后续需要产品或技术确认的问题。 |
| [12-rno-domain-and-metadata-detailed-spec.md](12-rno-domain-and-metadata-detailed-spec.md) | 继承 5 月文档的信息量，展开 RNO 样例域、分层模型、样例表、字段、血缘、YAML 和元数据演进细节。 |
| [13-agent-search-sandbox-detailed-spec.md](13-agent-search-sandbox-detailed-spec.md) | 展开 NL-to-Code Agent、LangGraph 节点、工具、语义检索、benchmark、沙箱和重试机制。 |
| [14-ui-x6-interaction-detailed-spec.md](14-ui-x6-interaction-detailed-spec.md) | 展开完整 UI 目标态，按页面、布局、操作、X6 画布、右键菜单和跨页面联动描述。 |
| [15-api-runtime-sdk-detailed-spec.md](15-api-runtime-sdk-detailed-spec.md) | 展开 Spring Boot API、GaussDB 表、SDK Builder、订阅、查询、通知、drift 和运行时序。 |
| [16-e2e-acceptance-detailed-spec.md](16-e2e-acceptance-detailed-spec.md) | 展开 Phase 1 到 Phase 7 的详细验收用例、命令、数据和预期结果。 |
| [17-feature-matrix-detailed.md](17-feature-matrix-detailed.md) | 以 5 月功能树为基准，逐项映射目标态、当前状态、迁移动作和验收方式。 |
| [18-api-parameter-matrix.md](18-api-parameter-matrix.md) | 展开正式 API 的请求参数、响应字段、校验规则、错误码和 DTO 口径。 |
| [19-project-structure-and-infra-detailed.md](19-project-structure-and-infra-detailed.md) | 展开目标项目结构、shared infra 复用、初始化、健康检查和本地运行方式。 |
| [20-source-coverage-map.md](20-source-coverage-map.md) | 对照 5 月和 6 月历史文档，逐节说明内容迁移到新文档集的位置。 |

## 3. 当前实施状态

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| Spring Boot governance-server | Implemented | 已具备正式元数据、血缘、订阅、查询、事件和 drift 的测试覆盖。 |
| 正式 API 前缀 | Implemented | 已使用 `/rest/oss/inner/modelengineservice/v1`。 |
| GaussDB 目标模型 | In progress | 当前本地运行可通过配置使用 H2 或目标数据源；目标文档以 GaussDB 为准。 |
| Docker governance runtime | Implemented | governance-server 可容器化运行，并复用共享基础设施网络。 |
| 正式字段级血缘 UI | Implemented | 当前图渲染为 G6 过渡实现。 |
| UI 可视化验收 | Implemented | Playwright headed 用例已覆盖正式血缘场景。 |
| X6 目标画布 | Planned | 血缘和 Pipeline 目标态统一迁移到 X6。 |
| FastAPI/Neo4j 迁移 | Planned | 旧元数据能力迁移到 Spring Boot + GaussDB。 |

## 4. 使用规则

- 新需求、实施计划和验收用例应优先引用本目录文档。
- 历史文档只作为来源和迁移依据，不再作为目标态权威口径。
- 如果实现与本文档冲突，应优先判断是文档需要更新，还是实现仍处于迁移阶段。
- 基础设施相关变更必须遵守仓库根目录 `AGENTS.md` 中的 shared infra 约束。
- 详细规格文档不是附录摘要，而是后续实施计划的主要信息来源；实现计划应优先引用 `12` 到 `16` 的具体用例和交互细节。
