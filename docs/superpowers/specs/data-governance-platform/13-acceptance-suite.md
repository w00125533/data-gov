# 13 验收套件

## 1. 文档和持久化口径

| # | 用例 | 步骤 | 预期 |
| --- | --- | --- | --- |
| A1 | 编号文档存在 | 查看 `data-governance-platform` | 存在 00-14 编号文档。 |
| A2 | 默认图数据库 | 搜索“图数据库默认” | 文档明确默认使用图数据库。 |
| A3 | GaussDB 兼容 | 搜索“GaussDB 兼容” | 文档保留关系模型兼容实现。 |
| A4 | 内部 API | 搜索 `/api/agent` 和 `/api/sandbox` | Agent 和沙箱 API 已定义。 |

## 2. RNO 和元数据

| # | 用例 | 步骤 | 预期 |
| --- | --- | --- | --- |
| M1 | RNO 10 表 | 注册样例域 | 10 张表存在。 |
| M2 | 字段级血缘 | 查询 `dws_cell_hourly.avg_sinr` 上游 | 返回 `dwd_session_qos.avg_sinr`。 |
| M3 | YAML 副本 | 导出 `dws_cell_hourly.yaml` | 包含 fields、binding、lineage。 |
| M4 | 删除保护 | 删除 `ods_ue_signal.rsrp` | 阻止并展示下游影响。 |

## 3. UI 和 Agent

| # | 用例 | 步骤 | 预期 |
| --- | --- | --- | --- |
| U1 | metadata 浏览 | `/metadata` 搜索“信噪比” | 命中 `avg_sinr`。 |
| U2 | X6 血缘 | `/metadata/lineage` 打开表 | X6 显示字段端口和边。 |
| U3 | Chat 正向 ETL | 输入小区小时 SINR 聚合 | 返回代码卡和 dry-run 按钮。 |
| U4 | 反向合成 | 输入用户评分造数 | 显示约束滑块。 |
| U5 | Schema Evolution | 确认字段 diff | 产生 Change/metadata_event。 |

## 4. 沙箱

| # | 用例 | 步骤 | 预期 |
| --- | --- | --- | --- |
| S1 | Spark SQL dry-run | POST `/api/sandbox/dry-runs` | 返回 runId 和 preview。 |
| S2 | Flink SQL dry-run | 提交窗口统计 | 返回 applicationId。 |
| S3 | Java Flink dry-run | 提交 DataStream 代码 | Maven 编译并提交。 |
| S4 | 自动重试 | 注入 `SLECT` | 自动修正并重试。 |

## 5. 订阅、查询、通知、drift

| # | 用例 | 步骤 | 预期 |
| --- | --- | --- | --- |
| Q1 | API query | 查询 `dws_cell_hourly` | 返回 rows 并写 query_record。 |
| Q2 | SQL Gateway | 执行只读 SELECT | 返回 rows。 |
| Q3 | Kafka topic 查询拒绝 | SQL 查询 TOPIC | 返回 `QUERY_NOT_ALLOWED`。 |
| Q4 | 订阅通知 | 修改订阅字段 | 生成 notification 并发 Kafka。 |
| Q5 | drift | 有查询无订阅 | 生成 `UNDECLARED_USAGE`。 |
