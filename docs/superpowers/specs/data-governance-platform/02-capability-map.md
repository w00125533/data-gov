# 02. 能力地图

## 1. 元数据管理

- 浏览元数据列表，支持关键词、领域、类型、负责人和状态过滤。
- 查看数据集详情，包括字段 schema、物理绑定、描述、查询开关和最近声明信息。
- 通过启动快照注册或运行时 API 修改元数据。
- 查看 YAML 表达、历史变更和字段表达式。
- 从元数据详情跳转血缘、Schema Evolution 和 Chat。

## 2. 血缘管理

- 查询指定 `metadataId` 的上游和下游。
- 同时返回表级边和字段级边。
- 字段级边包含源字段、目标字段、表达式、转换类型和作业标识。
- 目标 UI 使用 X6 表达字段端口和字段级连线。
- 支持边详情、影响分析、拖拽建边、右键维护和表达式编辑。

## 3. NL Agent

- 对话式理解正向 ETL、反向合成和元数据演进意图。
- 调用 schema lookup、语义搜索和血缘查询辅助生成。
- 生成 Spark SQL、Flink SQL 或 Java Flink。
- 发现缺失表或字段后生成补齐建议。
- 通过 Spring Boot 正式 API 提交 schema 或 lineage 变更。
- 对 dry-run 失败进行诊断和重试。

## 4. Pipeline

- 正向 ETL DAG 展示从 ODS 到 EVAL 的链路。
- 反向合成链路展示目标评估表到输入约束和数据生成器的回溯关系。
- 支持节点详情、上下游突出、模式切换、节点跳转 Chat 和跳转血缘。
- 目标态使用 X6 统一画布能力。

## 5. Schema Evolution

- 展示跨表变更时间线。
- 支持按表、字段、操作类型和关键词过滤。
- 展示字段表达式 diff、元数据 diff 和 YAML diff。
- 从变更记录跳转血缘图和元数据详情。

## 6. 订阅、查询、通知和 Drift

- 订阅表达使用意图和变化通知关注。
- 产品 API 和 SQL Gateway 产生查询事实。
- 元数据变化事件匹配订阅后生成通知并投递 Kafka。
- Drift 分析比较订阅声明、查询事实和启动快照刷新时间。

## 7. 沙箱和预览

- 编译和运行 Spark SQL、Flink SQL、Java Flink。
- 提交 YARN 并轮询终态。
- 读取 HDFS 或目标存储的预览结果。
- 将错误解析、重试记录和结果预览回填 Chat 或结果面板。

## 8. 健康检查

- Spring Boot governance-server health。
- Python Agent 服务 health。
- GaussDB、Kafka、StarRocks、Hive、Spark/YARN、Chroma 等依赖健康状态。
- UI 中展示异常高亮和最近检查时间。
