# 13. Agent、语义检索与沙箱详细规格

本文恢复 2026-05-13 文档中 NL-to-Code Agent、语义检索、benchmark、沙箱和双层重试的具体设计，并按目标态架构修订：Python 服务保留 Agent 能力，元数据主写入口改为 Spring Boot `/rest/oss/inner/modelengineservice/v1` API。

## 1. Agent 目标

Agent 面向三类用户意图：

| 意图 | 用户表达 | 目标产物 |
| --- | --- | --- |
| 正向 ETL | “用 UE 信号计算每小时小区平均覆盖强度，写入 dws_cell_hourly。” | Spark SQL、Flink SQL 或 Java Flink，字段映射和 dry-run 结果。 |
| 反向合成 | “给 eval_user_score 的评分流程造 10 行覆盖优秀、良好、差三档的数据。” | 约束反推、生成代码、写入各层数据、预览和分档图表。 |
| 元数据演进 | “给 dwd_session_qos 加 jitter 字段，用 latency 标准差计算。” | schema diff、血缘 diff、影响分析、确认后提交治理 API。 |

Agent 不直接操作 GaussDB。所有元数据、字段、血缘和订阅变更都通过 Spring Boot API 完成。

## 2. LangGraph 状态模型

Agent State 需要保存以下信息：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | string | 对话会话 ID。 |
| `messages` | list | 用户和系统消息。 |
| `intent` | enum | `forward_etl`、`reverse_synth`、`schema_evolve`、`unknown`。 |
| `context` | object | 从 UI 跳转带入的 table、field、metadataId、lineage edge、pipeline node。 |
| `matched_assets` | list | 语义搜索命中的候选数据集。 |
| `matched_fields` | list | 语义搜索命中的候选字段。 |
| `lineage_context` | object | 从 Spring Boot lineage API 查询到的上下游图。 |
| `schema_diff` | object | 元数据演进变更草案。 |
| `code_candidates` | list | 生成的 Spark/Flink/Java 代码。 |
| `dry_run_result` | object | 沙箱执行结果。 |
| `gap_result` | object | 缺失对象检测结果。 |
| `retry_count` | int | Agent 层重试次数。 |
| `final_answer` | string | 面向 UI 的最终解释。 |

## 3. LangGraph 节点

### 3.1 `classify_intent`

职责：

- 判断用户意图。
- 提取目标表、字段、指标、时间粒度、输出存储、行数和约束关键词。
- 根据 UI context 增强判断。例如从 `/metadata/lineage` 跳入 Chat 时，默认倾向 schema_evolve 或 forward_etl。

输入示例：

```text
把 dws_cell_hourly.drop_rate 的计算逻辑改成丢包率和切换失败率加权，权重 0.7/0.3。
```

输出示例：

```json
{
  "intent": "schema_evolve",
  "targetAssetCode": "dws_cell_hourly",
  "targetField": "drop_rate",
  "operation": "UPDATE_FIELD_EXPRESSION"
}
```

### 3.2 `schema_lookup`

职责：

- 调用 Spring Boot metadata API 查询候选数据集和详情。
- 调用 lineage API 获取上下游上下文。
- 调用语义搜索补充自然语言关键词匹配。

正式 API：

```http
GET /rest/oss/inner/modelengineservice/v1/metadata?keyword=...
GET /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}
GET /rest/oss/inner/modelengineservice/v1/metadata/{metadataId}/lineage?direction=up&depth=5
```

### 3.3 `gap_check`

职责：

- 判断现有元数据是否足以完成用户需求。
- 识别缺失表、缺失字段、缺失血缘或缺失物理绑定。

gap 类型：

| 类型 | 示例 | 建议处理 |
| --- | --- | --- |
| `missing_table` | “基站负载”没有对应表。 | 生成新 metadata 草案。 |
| `missing_field` | `dwd_session_qos` 缺少 `avg_sinr`。 | 生成字段补齐草案。 |
| `missing_lineage` | 字段存在但没有上游。 | 生成 lineage fieldMappings 草案。 |
| `not_queryable` | Kafka topic 被用于 SQL 查询。 | 建议物化到 Hive/Iceberg/StarRocks。 |
| `ambiguous_asset` | 多张表都匹配“质量”。 | 要求用户选择或给出候选对比。 |

### 3.4 `gap_proposal`

职责：

- 将 gap 转成可确认的补齐方案。
- 方案包括 metadata、fields、binding、lineage 和影响说明。

UI 展示：

- 建议表名。
- 层级。
- 存储类型。
- 字段清单。
- 上游来源。
- 是否自动继续。
- “确认并继续”、“我自己定义”、“跳过”三个操作。

### 3.5 `code_generate`

职责：

- 根据意图生成 Spark SQL、Flink SQL 或 Java Flink。
- 代码必须引用已注册 metadata 的 assetCode 或物理绑定。
- 生成时写出字段映射，便于后续 lineage 回写。

正向 ETL 代码要求：

- 有明确输入表。
- 有明确输出表。
- 有字段 select 或 projection。
- 聚合必须包含 group by。
- 时间窗口必须明确窗口字段和窗口粒度。
- 输出字段必须能映射到目标 metadata schema。

Flink SQL 代码要求：

- Kafka source 包含 topic、format、bootstrap servers。
- 窗口函数使用目标 Flink 版本支持的语法。
- sink 可以是 HDFS、Hive、StarRocks 或临时预览 sink。

Java Flink 代码要求：

- 包含 main class。
- 包含 source、transform、sink。
- 可被 Maven 模板编译。
- 不硬编码本地路径，使用模板注入配置。

### 3.6 `schema_validate`

职责：

- 对元数据演进草案做一致性校验。
- 调用 Spring Boot 校验能力或本地工具做预校验。

校验项：

- 表名和字段名合法。
- 字段类型合法。
- 删除字段不会破坏下游，或必须展示阻断原因。
- 表达式引用字段存在。
- 血缘边的源和目标可解析。
- Kafka topic 不设置 `queryable=true`。

### 3.7 `dry_run`

职责：

- 调用沙箱执行代码。
- 收集编译日志、提交日志、application id、预览结果。
- 失败时交给 `repair_from_error`。

### 3.8 `repair_from_error`

职责：

- 解析 Maven、Spark、Flink、SQL 语法、字段不存在、表不存在等错误。
- 给 code_generate 提供修复上下文。
- 最多执行配置的重试次数。

错误分类：

| 错误 | 识别方式 | 修复策略 |
| --- | --- | --- |
| SQL 拼写 | parser error / syntax error | 修复关键字或括号。 |
| 字段不存在 | cannot resolve column | 重新 schema_lookup。 |
| 表不存在 | table not found | gap_check 或修正 assetCode。 |
| 类型不匹配 | cannot cast / incompatible type | 增加 cast 或调整字段类型。 |
| Maven 编译失败 | compilation failure | 定位 Java 代码行并修复 imports/type。 |
| YARN 失败 | application failed | 汇总日志并决定是否重试。 |

## 4. Agent 工具集

| 工具 | 目标态实现 |
| --- | --- |
| `search_tables_by_keyword` | 语义搜索 + Spring Boot metadata 列表。 |
| `get_metadata_detail` | `GET /metadata/{metadataId}`。 |
| `get_lineage` | `GET /metadata/{metadataId}/lineage`。 |
| `propose_schema_change` | Python 生成草案，Spring Boot 校验。 |
| `apply_schema_change` | `PATCH /metadata/{metadataId}`。 |
| `generate_spark_sql` | LLM + 模板。 |
| `generate_flink_sql` | LLM + 模板。 |
| `generate_flink_java` | LLM + Maven 模板。 |
| `dry_run_code` | 沙箱控制器。 |
| `explain_result` | 面向 UI 的解释文本和结构化卡片。 |

## 5. 语义检索详细设计

### 5.1 检索空间

表级文档：

```json
{
  "id": "table:dws_cell_hourly",
  "text": "小区小时汇总，包含 avg_rsrp avg_sinr total_sessions drop_rate avg_throughput ho_success_rate",
  "metadata": {
    "assetCode": "dws_cell_hourly",
    "layer": "DWS",
    "sourceType": "HIVE"
  }
}
```

字段级文档：

```json
{
  "id": "field:dws_cell_hourly.avg_rsrp",
  "text": "小区小时平均 RSRP，来源 dwd_session_qos.avg_rsrp，表达式 avg(avg_rsrp)",
  "metadata": {
    "assetCode": "dws_cell_hourly",
    "fieldName": "avg_rsrp",
    "fieldType": "double"
  }
}
```

### 5.2 组件选型

| 组件 | 用途 |
| --- | --- |
| jieba | 中文分词和术语保护。 |
| BM25 | 关键词检索，适合表名、字段名、缩写和英文 token。 |
| bge-small-zh-v1.5 | 中文语义向量。 |
| ChromaDB | 本地向量存储。 |
| RRF | 融合 BM25 和 dense 排名。 |
| LLM rerank | 候选较多或语义模糊时兜底。 |

### 5.3 术语保护

术语词典：

```text
RSRP
RSRQ
SINR
QoS
QoE
IMSI
gNodeB
切换成功率
小区画像
网络健康
反向合成
字段血缘
```

分词前应保护这些 token，避免被拆散影响召回。

### 5.4 增量同步

触发条件：

- metadata 新增。
- metadata_field 新增、修改、删除。
- lineage_edge 新增或修改。
- YAML 导出后可选触发重建。

同步策略：

- 表级文档按 `metadata.updated_at` 判断是否重建。
- 字段级文档按 `metadata_field.updated_at` 判断是否重建。
- Chroma upsert 使用稳定 id。
- 删除字段时删除对应 field doc。

### 5.5 混合检索流程

```text
query
  -> normalize and protect terms
  -> BM25 search topK=30
  -> dense search topK=30
  -> RRF merge topK=20
  -> optional LLM rerank topK=8
  -> return assets and fields
```

RRF 公式：

```text
score(d) = sum(1 / (k + rank_i(d)))
```

建议 `k=60`。

### 5.6 Rerank 输出

Rerank 不只返回排序，还应返回原因：

```json
{
  "assetCode": "dws_cell_hourly",
  "fieldName": "avg_sinr",
  "score": 0.91,
  "reason": "用户查询信号质量，avg_sinr 是小区小时信干噪比核心指标"
}
```

## 6. Benchmark

测试集分三类：

| 类型 | 数量 | 构造方式 | 示例 |
| --- | --- | --- | --- |
| 规则生成 | 30 | 从字段描述做同义词替换和语序变化。 | “查小区小时平均覆盖强度”命中 `dws_cell_hourly.avg_rsrp`。 |
| LLM 生成 | 20 | 给 LLM 元数据，让它模拟不同角色提问。 | “哪个表能看邻区切换质量？”命中 `ads_neighbor_pair`。 |
| 对抗样本 | 10 | 模糊、歧义、跨域。 | “质量不好在哪里体现？”返回候选并要求澄清。 |

指标：

| 指标 | 目标 |
| --- | --- |
| Recall@5 | >= 0.90 |
| MRR@10 | >= 0.75 |
| 字段级 Recall@5 | >= 0.85 |
| 降级可用性 | dense 不可用时 BM25 仍返回结构化候选 |
| P95 延迟 | 本地检索 <= 800ms，不含 LLM rerank |

CI 门禁：

- 每次修改检索预处理、embedding、fusion、rerank 时运行 benchmark。
- 如果 Recall@5 下降超过 5%，需要说明原因或修复。

## 7. 沙箱详细设计

### 7.1 统一模型

```json
{
  "language": "SPARK_SQL | FLINK_SQL | FLINK_JAVA",
  "code": "string",
  "entryClass": "optional for Java",
  "runtimeConfig": {
    "queue": "default",
    "parallelism": 1,
    "timeoutSeconds": 120
  },
  "preview": {
    "enabled": true,
    "limit": 1
  }
}
```

### 7.2 模板结构

```text
templates/
  spark-sql/
    pom.xml
    src/main/java/.../SparkSqlRunner.java
  flink-sql/
    pom.xml
    src/main/java/.../FlinkSqlRunner.java
  flink-java/
    pom.xml
    src/main/java/.../GeneratedJob.java
```

模板注入变量：

- code。
- job name。
- input/output binding。
- checkpoint 或临时目录。
- preview sink。
- shared infra endpoint。

### 7.3 提交方式

Spark SQL：

```text
mvn package
spark-submit --master yarn --deploy-mode cluster generated-spark-job.jar
```

Flink SQL：

```text
mvn package
flink run -m yarn-cluster generated-flink-sql-job.jar
```

Java Flink：

```text
mvn package
flink run -m yarn-cluster -c com.example.GeneratedJob generated-flink-job.jar
```

### 7.4 资源限制

| 配置 | 默认值 |
| --- | --- |
| CPU | 1 core |
| Memory | 1G |
| Timeout | 120s |
| Preview rows | 1 到 20 |
| Max retry | 3 |
| Temporary dir TTL | 24h |

### 7.5 结果模型

```json
{
  "success": true,
  "compileLog": "maven output",
  "applicationId": "application_...",
  "yarnStatus": "FINISHED",
  "previewRows": [
    {"cell_id": "cell_001", "avg_rsrp": -93.2}
  ],
  "errors": [],
  "startedAt": "2026-06-14T10:00:00Z",
  "finishedAt": "2026-06-14T10:01:00Z"
}
```

### 7.6 双层重试

沙箱层重试：

- 编译失败。
- 临时依赖拉取失败。
- YARN 暂时性提交失败。
- 可自动修复的 SQL 语法错误。

Agent 层重试：

- 业务逻辑生成不满足 schema。
- 字段不存在需要重新 lookup。
- gap check 后需要补齐对象。
- 用户确认修改需求。

两个重试计数分开。沙箱内部重试不应消耗 Agent 多轮推理次数，除非需要 LLM 修复代码。

## 8. 与 UI 的结构化输出

Agent 返回给 UI 的内容不能只是自然语言，还应包含结构化 cards：

```json
{
  "intent": "forward_etl",
  "summary": "生成 dws_cell_hourly 小区小时汇总 SQL",
  "cards": [
    {"type": "matched_assets", "items": []},
    {"type": "code", "language": "spark_sql", "content": "..."},
    {"type": "lineage_preview", "edges": []},
    {"type": "dry_run_result", "success": true, "previewRows": []}
  ]
}
```

UI 依赖 cards 渲染代码、diff、血缘预览、gap 建议、dry-run 结果和图表。
