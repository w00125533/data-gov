# AGENTS.md

## 公共基础设施约束

- 新增或修改 Docker Compose 基础设施前，必须先检查 `../shared-data-infra` 是否已经定义同类服务或 profile。
- 如果 `../shared-data-infra` 已定义 HDFS、Hive Metastore、HiveServer2、Spark、YARN、Kafka、ZooKeeper、StarRocks、Prometheus、Grafana 等能力，不要在本工程重复新增；通过 external network、环境变量和项目级命名空间复用。
- 本工程本地只保留 backend、frontend、Chroma 数据卷等应用资源；Neo4j、HDFS/YARN/Hive/Kafka/StarRocks/Spark 工具容器应由 `../shared-data-infra` 提供。
- 修改基础设施后，至少运行 `docker compose -f ../shared-data-infra/compose.yaml --profile data-gov config` 和 `docker compose -f app-compose.yml config`。



## 文档刷新策略：
- 每次更新代码后，请同步检查一下对应章节的文档是否应该更新，如果需要请更新核心内容，如：功能描述、用例、逻辑图、运行流程、对外接口、UI 操作流程、数据模型。

## 文档图示约束

- 文档中的架构图、逻辑图、运行流程图统一使用 PlantUML，Markdown 代码块必须标记为 `plantuml`，不要新增 Mermaid 图。
- PlantUML 图必须包含 `@startuml` 和 `@enduml`，并优先使用 sequence/component/class/activity 等 PlantUML 原生表达。
- 二级功能章节中的图示顺序固定为：先写“逻辑图”，再写“运行流程”；标题中不要追加“（PlantUML）”。
