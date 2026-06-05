# AGENTS.md

## 公共基础设施约束

- 新增或修改 Docker Compose 基础设施前，必须先检查 `../shared-data-infra` 是否已经定义同类服务或 profile。
- 如果 `../shared-data-infra` 已定义 HDFS、Hive Metastore、HiveServer2、Spark、YARN、Kafka、ZooKeeper、StarRocks、Prometheus、Grafana 等能力，不要在本工程重复新增；通过 external network、环境变量和项目级命名空间复用。
- 本工程本地只保留应用状态和业务服务，例如 Neo4j、backend、frontend、Chroma 数据卷；HDFS/YARN/Hive/Kafka/StarRocks/Spark 工具容器应由 `../shared-data-infra` 提供。
- 修改基础设施后，至少运行 `docker compose -f base-compose.yml config` 和 `docker compose -f app-compose.yml config`。
