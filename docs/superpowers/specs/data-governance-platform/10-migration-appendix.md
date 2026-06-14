# 10. 迁移附录

## 1. 历史文档来源

| 历史文档 | 迁移处理 |
| --- | --- |
| `../archive/2026-05-13-wireless-rno-data-service-design.md` | 作为产品范围、UI 目标态、Agent、沙箱和 RNO 样例来源。 |
| `../archive/2026-06-10-data-product-governance-design.md` | 作为 Spring Boot、GaussDB、订阅、查询、通知和 drift 设计来源。 |
| `../archive/data-governance-2026-06-10/` | 作为旧 6 月 API、数据模型、运行时、架构视图和决策来源。 |

## 2. FastAPI 迁移

| 旧能力 | 目标迁移 |
| --- | --- |
| `/api/tables` | Spring Boot `/rest/.../metadata` |
| `/api/fields` | Spring Boot `/rest/.../metadata/{metadataId}` schema |
| `/api/lineage` | Spring Boot `/rest/.../metadata/{metadataId}/lineage` |
| `/api/pipeline` | Spring Boot 或 Python Agent 服务按目标边界重新定义，UI 最终通过稳定契约调用。 |
| `/api/schema/*` | 元数据演进写入 Spring Boot；LLM 推理和 diff 生成可由 Python Agent 协助。 |
| `/api/chat/*` | 保留 Python Agent 边界，正式元数据写入通过 Spring Boot API。 |

## 3. Neo4j 迁移

| 旧图模型 | 目标模型 |
| --- | --- |
| `Table` 节点 | `metadata` + `metadata_binding` |
| `Field` 节点 | `metadata_field` |
| `HAS_FIELD` | `metadata_field.metadata_id` 外键 |
| `DERIVES_FROM` | `lineage_edge` |
| `Change` | `metadata_event` 和 schema evolution 查询视图 |

迁移后，血缘遍历由 Spring Boot 根据 `lineage_edge` 递归或应用层遍历实现。

## 4. G6 到 X6 迁移

当前文件：

- `frontend/src/components/FormalLineageGraph.tsx`
- `frontend/src/components/LineageGraph.tsx`
- `frontend/src/components/PipelineDAG.tsx`
- `frontend/src/components/graphShared/`

目标迁移：

- 新建 X6 画布基础组件。
- 将 graphShared 数据转换层调整为节点、字段端口和边模型。
- 血缘图用字段端口表达字段级边。
- Pipeline DAG 用 X6 节点表达表、作业、约束和生成器。
- 保留 Playwright 可视化验收，覆盖画布加载、节点选择、边选择、缩放和详情同步。

## 5. Compose 迁移

旧方案中的本地基础设施 compose 不再作为目标态。目标态：

- `../shared-data-infra` 提供共享基础设施。
- `app-compose.yml` 只保留应用服务和应用级数据卷。
- 如果需要新增基础能力，先检查 shared infra 是否已存在同类服务或 profile。

## 6. API 前缀迁移

旧 `/api/...` 调用迁移到：

```text
/rest/oss/inner/modelengineservice/v1
```

前端和 SDK 新增能力不得继续扩展旧 `/api` 治理接口。Agent 或沙箱内部接口允许保留在 Python 服务边界内，但不能作为正式治理 API。
