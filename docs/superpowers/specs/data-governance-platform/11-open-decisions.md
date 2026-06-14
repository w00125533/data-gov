# 11. 决策记录

## 1. 已确认决策

| 决策 | 结论 |
| --- | --- |
| 平台命名 | 数据治理平台。 |
| 文档组织 | 新建 `data-governance-platform/` 文档集，旧文档归档。 |
| 目标架构主服务 | Spring Boot Governance Service。 |
| Python 定位 | Agent、搜索、沙箱和 LLM 能力服务，不作为元数据主写入口。 |
| 元数据主库 | GaussDB。 |
| Neo4j | 从目标态移除，作为历史实现迁移来源。 |
| 正式 API 前缀 | `/rest/oss/inner/modelengineservice/v1`。 |
| 基础设施 | 复用 `../shared-data-infra`。 |
| UI 范围 | 完整继承 2026-05-13 文档目标态。 |
| 图画布目标 | 血缘图和 Pipeline DAG 统一使用 AntV X6。 |
| 无线 RNO | 作为样例域和验收场景，不限定平台定位。 |

## 2. 后续需要确认的问题

| 问题 | 当前建议 |
| --- | --- |
| Python Agent 是否由 Spring Boot 代理所有前端请求 | 正式治理能力由 Spring Boot 承载；Chat/Sandbox 可先由前端直连 Python，再逐步收敛为 Spring Boot façade。 |
| X6 迁移是否一次性替换 G6 | 按血缘图优先、Pipeline 次之的顺序迁移，但目标态两者都使用 X6。 |
| 元数据演进确认流是否需要审批 | 第一阶段做用户确认，不做审批流；后续如接入治理审批再扩展。 |
| Flink/Spark 作业运行事实是否入库 | 第一阶段保留作业声明；查询事实先覆盖 API/SQL，后续增加 job run fact。 |
| StarRocks/Iceberg 自动建表默认策略 | 默认检查存在性，不默认自动建表；业务显式开启后创建。 |

## 3. 文档维护规则

- 已确认决策变更时，必须更新本文件。
- 若新实施计划改变目标范围，必须同步更新产品范围和验收用例。
- 若实现仍处于迁移阶段，不能把目标态降级为当前实现；应在 roadmap 标注状态。
