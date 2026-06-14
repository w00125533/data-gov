# 01. 产品范围

## 1. 平台目标

数据治理平台面向微服务、Flink、Spark、数据平台作业和治理管理员，统一管理数据集元数据、字段 schema、物理绑定、血缘、订阅、查询、通知、运行态使用事实和治理 drift。

平台同时保留 2026-05-13 版本提出的智能化能力：

- NL-to-Code Agent 生成 Spark SQL、Flink SQL 和 Java Flink 代码。
- 正向 ETL：用户描述目标数据集后，Agent 在已有数据上生成加工逻辑。
- 反向合成数据：用户给出评估 pipeline 后，Agent 反推输入约束并生成测试或压测数据。
- 元数据演进：用户通过自然语言变更表、字段、表达式和血缘。
- Web 可视化：元数据、字段级血缘、Pipeline、Schema Evolution、Chat、Sandbox 和 Health 统一呈现。

## 2. 业务样例域

无线 RNO 保留为默认样例域。它用于验证平台具备跨层、跨存储、跨运行模式的治理能力，但平台设计不限定为 RNO 专用。

样例分层：

| 层级 | 示例数据集 | 存储 |
| --- | --- | --- |
| L1 ODS | `ods_ue_signal`, `ods_gnb_alarm` | Kafka |
| L2 DWD | `dwd_session_qos`, `dwd_ho_event` | Hive / Iceberg |
| L3 DWS | `dws_cell_hourly`, `dws_area_traffic` | Hive / Iceberg |
| L4 ADS | `ads_cell_profile`, `ads_neighbor_pair` | StarRocks |
| L5 EVAL | `eval_user_score`, `eval_net_health` | StarRocks |

## 3. 目标能力范围

| 能力域 | 目标能力 |
| --- | --- |
| 元数据治理 | 注册、发现、详情、字段 schema、物理绑定、负责人、领域、查询开关、YAML 视图和变更历史。 |
| 血缘治理 | 表级血缘、字段级血缘、上下游查询、表达式、作业标识、影响分析、画布维护。 |
| 订阅治理 | 消费方声明、字段范围、使用模式、关注事件、取消订阅、订阅状态。 |
| 统一查询 | 产品 API 查询、SQL Gateway、只读校验、资产编码到物理表改写、查询记录。 |
| 事件通知 | 元数据事件、订阅匹配、Kafka 通知、SDK listener 回调。 |
| Drift 分析 | 声明未使用、未声明使用、长期未刷新声明。 |
| Agent | 意图识别、schema lookup、代码生成、gap check、schema evolve、dry-run retry、结果解释。 |
| 沙箱 | Spark/Flink/Java 编译、提交、YARN 状态、HDFS 结果回读、失败重试。 |
| UI | metadata、lineage、chat、pipeline、schema-evolution、sandbox/preview、health 全量目标态。 |
| 运行时观测 | 服务健康、共享基础设施健康、SDK 注册状态、查询事实和通知状态。 |

## 4. 范围边界

第一阶段不把 Python 服务作为治理主服务；Python 保留智能能力服务定位。第一阶段不把 Kafka topic 纳入统一查询，只将其作为可注册、可订阅、可血缘追踪的元数据对象。

目标态包括完整 UI 愿景，但实施计划允许分阶段落地。文档中的目标能力不能因为当前阶段未实现而删除，只能标注为 Planned 或 Future。
