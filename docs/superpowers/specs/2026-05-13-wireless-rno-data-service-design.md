# 无线网络感知数据语义化服务 — 设计文档

> 2026-05-13 | Status: Approved

## 1. 概述

构建一个语义化元数据管理 + 数据加工逻辑生成 + 反向样例数据生成的服务平台。

### 核心能力

1. **NL-to-Code Agent**：多轮自然语言对话，生成可执行 Flink SQL / Spark SQL / Java (Flink Stream API)
2. **正向 ETL**：用户描述目标数据集 → Agent 在已有数据 (Hive/Kafka/StarRocks) 上加工
3. **反向合成数据**：用户给出评估 pipeline → Agent 反推输入约束并生成测试/压测数据
4. **元数据演进**：通过自然语言增强元数据模型，自动更新字段、表达式、血缘
5. **Web 可视化**：元数据浏览、血缘工作台、正向/反向 pipeline 呈现

### 范围

全部 6 个子系统统一规划，按依赖顺序分 3 个 Phase 实现：

| Phase | 内容 |
|-------|------|
| Phase 1 | 基础设施 (Docker 栈) + 语义元数据服务 |
| Phase 2 | NL-to-Code Agent (LangGraph + DeepSeek) + 沙箱 |
| Phase 3 | Web 可视化 UI (React + Ant Design + AntV X6/G6) |

### 技术决策总表

| 决策点 | 选择 |
|--------|------|
| 后端框架 | Python FastAPI |
| 元数据存储 | Neo4j (图数据库, 表/字段/血缘统一持久化) |
| Agent 框架 | LangChain + LangGraph |
| 外部 LLM | DeepSeek (OpenAI 兼容接口) |
| 配置管理 | `.env` |
| Docker 编排 | base-compose (基础设施) + app-compose (应用) |
| 前端 | React 18 + TypeScript + Vite |
| UI 库 | Ant Design |
| 图可视化 | AntV X6 (血缘工作台) + AntV G6 (Pipeline DAG) |
| 沙箱提交 | 统一 Java 打包 + spark-submit / flink CLI（均提交到 YARN） |

### 功能树全景

> 说明：功能树按"用户能用的功能"组织，编号独立于下文 `## N.` 章节编号。下文章节按实现视角组织，二者编号不一定对应。

```
无线网络感知数据语义化服务
│
├── 1. 基础设施管理
│   ├── 1.1 Docker 栈一键启动/停止
│   ├── 1.2 初始化脚本执行
│   └── 1.3 配置管理 (.env)
│
├── 2. 元数据管理 (/metadata)
│   ├── 2.1 浏览
│   │   ├── 2.1.1 分层过滤 (L1~L5)
│   │   ├── 2.1.2 搜索 (表名/字段/描述)
│   │   └── 2.1.3 表详情展示 (字段+表达式+上游)
│   ├── 2.2 维护
│   │   ├── 2.2.1 新建表 (含字段定义)
│   │   ├── 2.2.2 编辑表 (层/存储/描述)
│   │   ├── 2.2.3 删除表 (下游依赖警告)
│   │   ├── 2.2.4 新建字段
│   │   ├── 2.2.5 编辑字段 (Monaco 表达式编辑器)
│   │   └── 2.2.6 删除字段 (断链警告)
│   ├── 2.3 YAML 管理
│   │   ├── 2.3.1 导出全量/单表 YAML
│   │   ├── 2.3.2 YAML 预览 (只读)
│   │   └── 2.3.3 YAML 版本 diff (git)
│   └── 2.4 跳转演化历史
│       └── 表详情页 [演化历史] → /schema-evolution?table=xxx
│
├── 3. 血缘图 (/metadata/lineage)
│   ├── 3.1 可视化
│   │   ├── 3.1.1 表级血缘主图 (X6 Graph)
│   │   ├── 3.1.2 前向/后向 checkbox 显示控制
│   │   ├── 3.1.3 表节点展开后显示字段行与字段级虚线血缘
│   │   ├── 3.1.4 节点拖拽 + 缩放
│   │   ├── 3.1.5 边详情 (点击查看计算类型、参数、转换表达式)
│   │   ├── 3.1.6 Mini-map 导航
│   │   └── 3.1.7 全屏模式
│   ├── 3.2 维护 (右键菜单)
│   │   ├── 3.2.1 编辑节点 (表/字段)
│   │   ├── 3.2.2 新建血缘边 (字段锚点连线)
│   │   ├── 3.2.3 编辑边计算类型、参数与表达式
│   │   ├── 3.2.4 删除边/节点
│   │   ├── 3.2.5 拖动边端点修改源/目标字段
│   │   ├── 3.2.6 基于血缘生成当前表 SQL
│   │   └── 3.2.7 粘贴 SELECT SQL 解析表定义与血缘
│   └── 3.3 与流程 3 联动
│       ├── 3.3.1 右键跳转 /chat (自动注入上下文)
│       ├── 3.3.2 NL 修改后自动刷新血缘图和 SQL 预览
│       └── 3.3.3 新建对象后血缘图实时更新
│
├── 4. NL 对话 (/chat)
│   ├── 4.1 对话管理
│   │   ├── 4.1.1 新建对话
│   │   ├── 4.1.2 对话历史列表
│   │   ├── 4.1.3 SSE 流式输出
│   │   ├── 4.1.4 意图识别 badge (正向ETL/反向合成/元数据演进)
│   │   └── 4.1.5 上下文注入 (从 /metadata /lineage /pipeline 跳转)
│   ├── 4.2 正向 ETL 流程
│   │   ├── 4.2.1 业务语义 → 表/字段自动匹配 (search_tables_by_keyword)
│   │   ├── 4.2.2 候选表推荐 (血缘预览 + 方案对比)
│   │   ├── 4.2.3 代码生成 (Spark SQL / Flink SQL / Java Flink)
│   │   ├── 4.2.4 代码卡片展示 (Monaco 高亮, 可编辑)
│   │   ├── 4.2.5 沙箱试跑 (YARN 提交)
│   │   ├── 4.2.6 预览结果表格 (1 行)
│   │   ├── 4.2.7 缺失对象自动补齐子流程 (gap_check → schema_evolve)
│   │   └── 4.2.8 失败自动重试 (最多 3 轮)
│   ├── 4.3 反向合成流程
│   │   ├── 4.3.1 业务语义 → 评估 pipeline 匹配
│   │   ├── 4.3.2 全链路上游溯源 (pipeline_parse)
│   │   ├── 4.3.3 约束反推面板 (表格: 变量 → 值域)
│   │   ├── 4.3.4 分档约束滑块调整 (值域 + 行数)
│   │   ├── 4.3.5 缺失对象自动补齐子流程
│   │   ├── 4.3.6 数据生成代码产出 (Java Flink 逐层回溯)
│   │   ├── 4.3.7 沙箱执行 + 分层写入
│   │   ├── 4.3.8 结果预览 (表格 + 分档柱状图)
│   │   └── 4.3.9 生成数据写入各表对应存储 (Kafka/Hive/StarRocks)
│   └── 4.4 元数据演进流程
│       ├── 4.4.1 业务语义 → 目标表/字段匹配
│       ├── 4.4.2 变更一致性校验 (重名/断链/循环依赖)
│       ├── 4.4.3 Diff 对比面板 (旧 vs 新, 左右对照)
│       ├── 4.4.4 下游影响分析 + 警告
│       ├── 4.4.5 确认后写入 Neo4j + 重写 YAML
│       └── 4.4.6 变更历史记录 (版本 + 旧值留痕)
│   └── 4.5 语义检索 (search_tables_by_keyword)
│       ├── 4.5.1 BM25 倒排索引 (jieba 分词 + 术语保护)
│       ├── 4.5.2 Dense 向量检索 (bge-small-zh-v1.5 + ChromaDB)
│       ├── 4.5.3 RRF 融合 + LLM Rerank 兜底
│       └── 4.5.4 增量同步 (Neo4j Field.version → ChromaDB upsert)
│
├── 5. Pipeline 可视化 (/pipeline)
│   ├── 5.1 正向 ETL DAG
│   │   ├── 5.1.1 完整链路展示 (ODS → EVAL, G6 DAG)
│   │   ├── 5.1.2 选中表上下游突出 + 层级滑块
│   │   ├── 5.1.3 节点悬浮: 表信息卡片 (字段/存储/表达式)
│   │   └── 5.1.4 右键 [💬 NL 查询] → /chat 上下文注入
│   ├── 5.2 反向合成链路
│   │   ├── 5.2.1 逆向图: 目标表 → 约束推断 → 生成器
│   │   ├── 5.2.2 每层约束气泡展示
│   │   └── 5.2.3 图上直接调整约束值域
│   └── 5.3 联动
│       ├── 5.3.1 与 /chat 联动 (图上操作跳转对话)
│       ├── 5.3.2 与 /metadata/lineage 联动 (共享图数据和层级配色)
│       └── 5.3.3 正向/反向一键切换
│
├── 6. 元数据演进历史 (/schema-evolution)
│   ├── 6.1 变更时间线 (按时间倒序, 跨所有表)
│   ├── 6.2 按表/字段/操作类型过滤
│   ├── 6.3 变更详情展开 (旧值→新值 diff)
│   ├── 6.4 YAML 版本 git diff (调用 git show)
│   └── 6.5 从 /metadata 表详情跳转 (?table= 预过滤)
│
├── 7. Sandbox 沙箱
│   ├── 7.1 Maven 编译
│   ├── 7.2 spark-submit / flink CLI 提交 (均到 YARN)
│   ├── 7.3 HDFS 结果回读
│   ├── 7.4 自动重试 (编译失败/执行失败)
│   └── 7.5 临时目录自动清理
│
└── 8. 健康检查面板 (/health)
    ├── 8.1 各组件连通性状态卡片
    ├── 8.2 自动刷新 (30s)
    └── 8.3 异常组件高亮提示
```

---

## 2. 元数据设计

### 2.1 分层结构

```
L1 接入层 (ODS)         L2 明细层 (DWD)        L3 汇总层 (DWS)        L4 宽表层 (ADS)        L5 评估层 (EVAL)
┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ ods_ue_signal │      │dwd_session_qos│     │dws_cell_hourly│     │ads_cell_profile│     │eval_user_score│
│ ods_gnb_alarm │      │dwd_ho_event   │     │dws_area_traffic│    │ads_neighbor_pair│    │eval_net_health│
└──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
```

### 2.2 10 张样例表

| # | 表名 | 层 | 存储类型 | 核心字段 | 上游依赖 |
|---|------|-----|----------|----------|----------|
| 1 | `ods_ue_signal` | L1-ODS | Kafka | imsi, cell_id, rsrp, rsrq, sinr, timestamp | 无 (原始采集) |
| 2 | `ods_gnb_alarm` | L1-ODS | Kafka | gnb_id, alarm_type, severity, alarm_time, duration | 无 |
| 3 | `dwd_session_qos` | L2-DWD | Hive | session_id, imsi, avg_rsrp, avg_rsrq, avg_sinr, packet_loss, latency, throughput | `ods_ue_signal` |
| 4 | `dwd_ho_event` | L2-DWD | Hive | imsi, source_cell, target_cell, ho_type, ho_result, ho_cause, ho_latency | `ods_ue_signal` |
| 5 | `dws_cell_hourly` | L3-DWS | Hive | cell_id, hour_bucket, avg_rsrp, avg_sinr, total_sessions, drop_rate, avg_throughput, ho_success_rate | `dwd_session_qos`, `dwd_ho_event` |
| 6 | `dws_area_traffic` | L3-DWS | Hive | area_id, hour_bucket, total_throughput, active_users, avg_latency, peak_throughput | `dwd_session_qos` |
| 7 | `ads_cell_profile` | L4-ADS | StarRocks | cell_id, date, coverage_score, capacity_score, stability_score, composite_kpi | `dws_cell_hourly` |
| 8 | `ads_neighbor_pair` | L4-ADS | StarRocks | source_cell, target_cell, ho_count, ho_success_rate, avg_ho_latency, recommend_priority | `dwd_ho_event` |
| 9 | `eval_user_score` | L5-EVAL | StarRocks | imsi, date, qoe_score, signal_quality, mobility_score, service_continuity | `ads_cell_profile` |
| 10 | `eval_net_health` | L5-EVAL | StarRocks | area_id, date, health_index, alarm_severity_weighted, user_complaint_ratio, degradation_trend | `dws_area_traffic`, `ods_gnb_alarm`, `eval_user_score` |

#### 2.2.1 示例表默认分类与标签纳管

元数据管理左侧导航采用“主分类树 + 标签”的混合模型。每张表必须且只能有一个主分类路径，标签可多选。以下映射作为种子数据初始化到 Neo4j；后续可在 `/metadata` 分类/标签管理界面调整。

| 表名 | 默认主分类路径 | 默认标签 |
|------|----------------|----------|
| `ods_ue_signal` | `源数据 / CHR` | `覆盖`, `质量`, `射频`, `标识信息` |
| `ods_gnb_alarm` | `源数据 / 配置` | `BBU`, `电源`, `机房`, `质量` |
| `dwd_session_qos` | `网络 / 质量` | `速率`, `时延`, `丢包`, `保持`, `标识信息` |
| `dwd_ho_event` | `网络 / 移动` | `保持`, `接入`, `质量`, `标识信息` |
| `dws_cell_hourly` | `网络 / 覆盖` | `话务`, `速率`, `保持`, `质量` |
| `dws_area_traffic` | `网络 / 话务` | `容量`, `速率`, `时延`, `活动信息` |
| `ads_cell_profile` | `网络 / 覆盖` | `容量`, `质量`, `射频` |
| `ads_neighbor_pair` | `网络 / 移动` | `保持`, `质量`, `工参` |
| `eval_user_score` | `用户 / 业务信息` | `覆盖`, `移动`, `业务信息`, `活动信息` |
| `eval_net_health` | `网络 / 质量` | `覆盖`, `话务`, `机房`, `业务信息` |

默认分类树初始化如下：

| 大分类 | 小分类 |
|------|------|
| 环境 | 地理、场景、天气、机房 |
| 设备 | 前传、时钟、回传、天馈、电源、射频、BBU |
| 网络 | 覆盖、干扰、话务、容量、速率、时延、质量、接入、保持、移动、丢包、能耗 |
| 用户 | 标识信息、终端信息、套餐信息、位置信息、业务信息、活动信息 |
| 业务 | 直播、视频、游戏、网页、扫码、上传下载、即时通信、生产、Mobile AI |
| 源数据 | 话统、CHR、配置、工参、电子地图 |

### 2.3 Neo4j Schema

技术栈中已不再使用 SQLite。表/字段/血缘/审计变更全部以图模型持久化在 Neo4j。

#### 节点

```cypher
// 表节点
(:Table {
    id,                  // 内部稳定 ID (UUID)
    name,                // 表名 (业务唯一)
    layer,               // ODS / DWD / DWS / ADS / EVAL
    layer_priority,
    description,
    storage_type,        // KAFKA / HIVE / STARROCKS
    sql_logic,           // 可空: 当前表级计算 SQL (Spark/Hive SELECT 片段)
    sql_dialect,         // 可空: spark_hive
    sql_source,          // generated / imported / manual
    sql_updated_at       // datetime, SQL 逻辑保存时间
})

// 字段节点
(:Field {
    id,                  // 内部稳定 ID (UUID)
    name,                // 字段名 (在所属表内唯一)
    field_type,          // STRING / INT / BIGINT / DOUBLE / TIMESTAMP
    is_nullable,         // bool
    is_partition,        // bool (表的分区键 = 所属表中 is_partition=true 的字段集)
    expression,          // 计算表达式 (SQL fragment)
    description,
    version,             // int, 默认 1
    previous_expr        // JSON 字符串: [{"v":1,"expr":"..."}]
})

// 元数据变更审计节点 (schema_evolve 路径写入)
(:Change {
    id,
    target_type,         // TABLE / FIELD / CATEGORY / TAG / TAG_GROUP
    target_id,           // target node id snapshot
    table_name,          // 字符串字段, 删除目标后仍可查
    field_name,          // 可空 (表级变更时为空)
    operation,           // ADD_TABLE / ADD_FIELD / UPDATE_FIELD / DELETE_FIELD / DELETE_TABLE
    version,             // 变更后版本号
    commit_hash,         // git commit hash, schema_apply 同步 commit 后回填
    old_value,           // JSON 字符串, 旧值快照
    new_value,           // JSON 字符串, 新值快照
    changed_at           // ISO8601 字符串
})

// 元数据分类节点
(:MetaCategory {
    id,
    code,                // stable business code
    name,
    level,               // 1 = root category, 2 = child category
    sort_order,
    protected,           // built-in root category protection
    active,
    created_at,
    updated_at
})

// 标签分组节点
(:MetaTagGroup {
    id,
    code,
    name,
    sort_order,
    active,
    created_at,
    updated_at
})

// 标签节点
(:MetaTag {
    id,
    code,
    name,
    sort_order,
    active,
    created_at,
    updated_at
})
```

#### 关系

```cypher
// 表-字段隶属关系
(Table)-[:HAS_FIELD]->(Field)

// 字段级血缘 (target 由 upstream 派生; 语义等同旧 upstream_field_refs)
(Field)-[:DERIVES_FROM {
    edge_id,
    transform_expr,
    calc_type,           // DIRECT / EXPRESSION / AGGREGATE / JOIN / WINDOW / CONDITION / CONSTANT
    calc_params,         // JSON 字符串: 计算类型参数
    created_at,
    updated_at
}]->(Field)

// Category tree
(MetaCategory)-[:HAS_CHILD]->(MetaCategory)

// Table primary category. Each table has exactly one active leaf category.
(Table)-[:IN_CATEGORY]->(MetaCategory)

// Tag group and flat tags
(MetaTagGroup)-[:HAS_TAG]->(MetaTag)

// Table tags. Each table can have zero or more tags.
(Table)-[:TAGGED_WITH]->(MetaTag)
```

#### 约束与索引

```cypher
CREATE CONSTRAINT table_id_unique FOR (t:Table) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT table_name_unique FOR (t:Table) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT field_id_unique FOR (f:Field) REQUIRE f.id IS UNIQUE;
CREATE CONSTRAINT change_id_unique FOR (c:Change) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT category_id_unique FOR (c:MetaCategory) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT category_code_unique FOR (c:MetaCategory) REQUIRE c.code IS UNIQUE;
CREATE CONSTRAINT tag_group_id_unique FOR (g:MetaTagGroup) REQUIRE g.id IS UNIQUE;
CREATE CONSTRAINT tag_group_code_unique FOR (g:MetaTagGroup) REQUIRE g.code IS UNIQUE;
CREATE CONSTRAINT tag_id_unique FOR (t:MetaTag) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT tag_code_unique FOR (t:MetaTag) REQUIRE t.code IS UNIQUE;

CREATE INDEX field_name_idx FOR (f:Field) ON (f.name);
CREATE INDEX change_changed_at_idx FOR (c:Change) ON (c.changed_at);
CREATE INDEX change_table_name_idx FOR (c:Change) ON (c.table_name);
CREATE INDEX category_name_idx FOR (c:MetaCategory) ON (c.name);
CREATE INDEX category_sort_idx FOR (c:MetaCategory) ON (c.sort_order);
CREATE INDEX tag_name_idx FOR (t:MetaTag) ON (t.name);
```

应用层强制约束（写入前 Cypher 校验）：
- `(t:Table)-[:HAS_FIELD]->(f:Field)` 在同一 `(t.name, f.name)` 维度唯一
- `DERIVES_FROM` 不能成环：写入新边前执行 `MATCH (target)-[:DERIVES_FROM*1..]->(target) RETURN count(*)`，结果必须为 0
- `DERIVES_FROM.calc_type` 必须来自固定枚举；`calc_params` 必须符合该计算类型的最小参数约束
- `Table.sql_logic` 只保存当前生效或用户确认同步的 SQL，不保存历史版本；历史 SQL 进入 `Change.old_value/new_value`
- 每张 `Table` 必须且只能有一个主分类；历史未分类表在 API 层归入虚拟“未归类”，编辑保存时必须选择真实叶子分类
- 内置大分类不允许硬删除；分类或标签被表引用时第一版只允许停用，不做物理删除

#### 写入语义

- 单 Neo4j 事务内同时写元数据节点/边 + 创建对应 `Change` 节点；失败原子回滚
- 审计 `Change` 节点为孤立节点，不与 Table/Field 建关系：删除操作的目标节点已不存在，关系会丢，字符串属性 `table_name`/`field_name` 独立保存即可。审计为只读追加日志，不参与图遍历
- 血缘图编辑动作即时写入 `DERIVES_FROM`；写入成功后前端重新拉取规范化图数据并刷新 SQL 预览
- SQL 逻辑预览不自动覆盖 `Table.sql_logic`；第一版通过 SQL 导入抽屉的“确认应用”写入 Table 节点并追加 `Change`，右侧 SQL 预览区的“同步到表定义”按钮先保留为后续直接写回入口
- 分类、标签、标签分组的新增、改名、移动、排序、停用均写入 `Change`
- 表主分类变更和表标签集合变更写入 `Change`；第一版只提供审计查看，不提供版本回滚

#### 派生查询

不在图中冗余存储以下信息，全部由 Cypher 实时计算：

- 字段级血缘 DAG：`MATCH path=(f:Field {id:$id})-[:DERIVES_FROM*1..$d]->(u) RETURN path`
- 表级血缘聚合：`MATCH (t1:Table)-[:HAS_FIELD]->(f1)-[:DERIVES_FROM]->(f2)<-[:HAS_FIELD]-(t2) RETURN t1, t2, count(*) AS edge_weight`
- 表分区键集合：`MATCH (t:Table {name:$n})-[:HAS_FIELD]->(f:Field {is_partition:true}) RETURN f.name`
- 血缘工作台图数据：以目标表为中心实时聚合表节点、表级边、字段清单和字段级边；不在 Neo4j 中冗余表级边
- 表 SQL 预览：根据当前目标表字段、直接上游 `DERIVES_FROM` 边、`calc_type/calc_params/transform_expr` 生成 Spark/Hive SELECT SQL
- 分类树：`MATCH p=(root:MetaCategory {level:1})-[:HAS_CHILD*0..]->(c:MetaCategory) RETURN p ORDER BY root.sort_order, c.sort_order`
- 分类过滤表：`MATCH (t:Table)-[:IN_CATEGORY]->(c:MetaCategory)`；勾选“含子类”时先展开目标分类后代再过滤
- 标签过滤表：`MATCH (t:Table)-[:TAGGED_WITH]->(tag:MetaTag)`；`tag_match=all` 时要求表拥有全部选中标签，`tag_match=any` 时拥有任一标签即可
- 分类和标签 API 使用稳定 ID：分类为 `category:<MetaCategory.code>`，标签为 `tag:<MetaTag.code>`；展示名称可编辑但不作为关系写入和过滤依据。

### 2.4 元数据演进策略

- 通过 NL 驱动元数据变更 (schema_evolve 路径)
- 增/删/改字段前执行一致性校验 (循环依赖检测、断链检测)
- 变更记录 version + previous_expr 留痕（Neo4j 中 Field 节点属性 + `Change` 节点轻量版本链），非完整 temporal versioning
- YAML 文件纳入 git 版本控制，提供 git diff 级别的完整历史追溯（与 Neo4j 内 version 链互补：version 链用于逻辑追溯，git diff 用于 YAML 级别的审计和回滚）

### 2.5 YAML 元数据副本

每张表在 Neo4j 之外同步生成一份 YAML 文件，用于人工查阅和版本 diff。存储路径：

```
metadata-yaml/
├── L1-ODS/
│   ├── ods_ue_signal.yaml
│   └── ods_gnb_alarm.yaml
├── L2-DWD/
│   ├── dwd_session_qos.yaml
│   └── dwd_ho_event.yaml
├── L3-DWS/
│   ├── dws_cell_hourly.yaml
│   └── dws_area_traffic.yaml
├── L4-ADS/
│   ├── ads_cell_profile.yaml
│   └── ads_neighbor_pair.yaml
└── L5-EVAL/
    ├── eval_user_score.yaml
    └── eval_net_health.yaml
```

YAML 格式示例 (`dws_cell_hourly.yaml`):

```yaml
table_name: dws_cell_hourly
layer: DWS
layer_priority: 3
description: 小区小时粒度汇总指标
storage_type: HIVE
fields:
  - name: cell_id
    type: STRING
    nullable: false
    partition: false
    description: 小区标识
    # 无 expression → 原始字段，来自上游
    upstream:
      - table: dwd_session_qos
        field: cell_id
  - name: hour_bucket
    type: TIMESTAMP
    nullable: false
    partition: true
    description: 小时窗口起点
    expression: "DATE_TRUNC('HOUR', timestamp)"
    upstream:
      - table: dwd_session_qos
        field: timestamp
  - name: avg_rsrp
    type: DOUBLE
    nullable: true
    description: 小区小时平均 RSRP
    expression: "AVG(rsrp)"
    upstream:
      - table: dwd_session_qos
        field: avg_rsrp
  - name: avg_sinr
    type: DOUBLE
    nullable: true
    description: 小区小时平均 SINR
    expression: "AVG(sinr)"
    upstream:
      - table: dwd_session_qos
        field: avg_sinr
  - name: total_sessions
    type: BIGINT
    nullable: true
    description: 会话总数
    expression: "COUNT(DISTINCT session_id)"
    upstream:
      - table: dwd_session_qos
        field: session_id
  - name: drop_rate
    type: DOUBLE
    nullable: true
    description: 掉话率
    expression: "CAST(SUM(CASE WHEN drop_flag=1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*)"
    upstream:
      - table: dwd_session_qos
        field: drop_flag
  - name: avg_throughput
    type: DOUBLE
    nullable: true
    description: 平均吞吐量 (Mbps)
    expression: "AVG(throughput)"
    upstream:
      - table: dwd_session_qos
        field: throughput
  - name: ho_success_rate
    type: DOUBLE
    nullable: true
    description: 切换成功率
    expression: "CAST(SUM(CASE WHEN ho_result='SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*)"
    upstream:
      - table: dwd_ho_event
        field: ho_result
```

- Neo4j 为运行时权威数据源，YAML 为人工可读副本
- 元数据演进 (schema_evolve) 变更应用后，同步重写对应 YAML 文件
- YAML 纳入 git 版本控制，变更历史可通过 git diff 追溯

---

## 3. Docker 一体化验证栈

### 3.1 Base Compose (基础设施，常驻)

| 服务 | 端口 | 说明 |
|------|------|------|
| HDFS NameNode | 9870 / 8020 | Spark / Flink 读写 |
| HDFS DataNode | 9864 | 数据节点 (1 个) |
| YARN ResourceManager | 8088 / 8032 | 统一资源调度 |
| YARN NodeManager | 8042 | 执行容器 (1 个) |
| Hive Metastore | 9083 | Spark SQL 外部表元数据 |
| HMS DB (Postgres) | 15432 | HMS 后端 |
| Kafka Broker | 9092 | KRaft 模式 (无 ZK) |
| StarRocks FE | 9030 / 8030 | OLAP 查询 |
| StarRocks BE | 9060 | 存储计算 |
| Neo4j | 7474 (Browser) / 7687 (Bolt) | 元数据 + 血缘唯一权威数据源；APOC plugin；`./data/neo4j/` 卷持久化；`neo4j:5-community` 镜像 |

### 3.2 App Compose (应用层，独立启停)

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI App | 8000 | 元数据 API + Agent + 沙箱控制器 |
| React Dev Server | 5173 | Vite HMR |

### 3.3 FastAPI 容器能力

```dockerfile
FROM python:3.11-slim
RUN apt-get install -y openjdk-17-jdk-headless maven
RUN pip install pyspark==3.5.4   # 含 spark-submit, SparkSession
# Flink 提交通过 subprocess: flink run -m yarn-cluster
```

### 3.4 存储流向

- ODS 层 → Kafka topic
- DWD / DWS 层 → Hive 外部表 (Parquet on HDFS)
- ADS / EVAL 层 → StarRocks (OLAP)

### 3.5 初始化

```
init-scripts/
├── 01_hive_init.sql
├── 02_kafka_init.sh
├── 03_starrocks_init.sql
├── 04_sample_data.py          # 反向合成小批量数据，灌入 Hive + StarRocks
├── 05_neo4j_init.py           # 创建约束/索引 (Constraint + Index DDL)
├── 06_neo4j_seed.py           # 10 张表 + ~70 字段 + 字段级血缘边写入 Neo4j
└── 07_export_yaml.py          # Neo4j → metadata-yaml/ 导出 YAML
```

### 3.6 服务健康检查面板

Web UI 提供健康检查面板（路由 `/health`），展示各组件连通性状态：

| 组件 | 检查方式 | 正常指标 |
|------|---------|----------|
| FastAPI | GET `/api/health` | 200 + uptime |
| Neo4j | Bolt `RETURN 1` | < 5ms |
| HDFS NameNode | HTTP `:9870/jmx` | State=active |
| YARN RM | HTTP `:8088/ws/v1/cluster/info` | started=true |
| Hive Metastore | Thrift connect `:9083` | connected |
| Kafka Broker | AdminClient `:9092` | broker count > 0 |
| StarRocks FE | MySQL query `:9030` | connected |
| ChromaDB | heartbeat query | connected |
| DeepSeek API | HTTP ping (可选) | 200 OK |

后端 API：`GET /api/health` 返回 JSON：

```json
{
  "status": "healthy",
  "uptime_seconds": 1234,
  "components": {
    "neo4j": {"status": "ok", "latency_ms": 3.2, "node_count": 80},
    "hdfs": {"status": "ok", "state": "active"},
    "yarn": {"status": "ok", "nodes": 1},
    "hive": {"status": "ok"},
    "kafka": {"status": "ok", "brokers": 1},
    "starrocks": {"status": "ok"},
    "chromadb": {"status": "ok", "doc_count": 80},
    "deepseek": {"status": "ok"}
  }
}
```

> FastAPI 自身的状态由顶层 `status` 字段反映（能成功返回 200 即 healthy），故不重复列入 `components`。

前端健康面板组件 `HealthPanel.tsx` 使用 Ant Design `Card` + `Badge` 网格布局，每组件一张状态卡片，自动刷新间隔 30s。

---

## 4. NL-to-Code Agent

### 4.1 LangGraph StateGraph

```
               ┌───────────┐
    START ────→│ classifier │
               └─────┬─────┘
          ┌──────────┼──────────┐
          ▼          ▼          ▼
    ┌──────────┐┌──────────┐┌────────────────┐
    │forward   ││reverse   ││schema_evolve   │
    │_etl      ││_synth    ││                │
    └────┬─────┘└────┬─────┘└───────┬────────┘
         │           │             │
         ▼           ▼        ┌────┴────────┐
    ┌─────────┐┌──────────┐   │schema_validate│
    │schema   ││pipeline  │   └──────┬────────┘
    │_lookup  ││_parse    │   ┌──────┴────────┐
    └────┬────┘└─────┬────┘   │schema_apply    │
         │           │        │(写入Neo4j)      │
         ▼           ▼        └──────┬────────┘
    ┌────────────────────────────┐  │
    │   gap_check                │  │
    │  (检查业务实体→表/字段映射)   │  │
    └───────────┬────────────────┘  │
                │                   │
         ┌──────┴──────┐            │
         ▼             ▼            │
    无缺失 / 完整   有缺失           │
         │             │            │
         ▼             ▼            │
    code_generate  ┌─────────────┐  │
                   │gap_proposal │  │
                   │(生成补齐建议) │  │
                   └──────┬──────┘  │
                          │         │
                          ▼         │
                   ┌──────────────┐ │
                   │schema_evolve │←┘
                   │(子流程,自动执行)│
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │schema_lookup │
                   │(回查补齐后Schema)│
                   └──────┬───────┘
                          │
                          ▼
                     code_generate
                          │
         ┌────────────────┘
         ▼
    ┌────────┐
    │dry_run │
    └───┬────┘
        ▼
   ┌──────────┐
   │presenter │
   └────┬─────┘
        ▼
      END
```

#### 节点逐一细化

> **节点契约**：所有节点遵循 LangGraph 约定 — 函数签名 `(state: AgentState) -> dict`，返回 partial dict 由 LangGraph merge 进 State；错误通过 `error_feedback` 字段传递；LLM 调用统一通过 DeepSeek 客户端（4.4 节）；调用工具时复用 4.3 节定义。**Prompts 关键约束** 仅在节点内列举必要要点（输出 JSON / 字段名 / temperature），完整 prompt 模板留给后续 Prompts 工程章节。

##### `classifier`

- **作用**: 识别用户输入的业务意图，路由到 forward_etl / reverse_synth / schema_evolve 三条主路径之一。
- **触发**: START（每条新对话）；多轮中检测到意图切换时。
- **输入** (State): `messages[-3:]`、`intent` (上一轮)、`context_source`。
- **输出** (State): `intent` ∈ {"forward_etl", "reverse_synth", "schema_evolve"}、`needs_clarification`。
- **LLM 调用**: 是 — DeepSeek Chat；JSON 输出 `{"intent", "confidence", "reason"}`；`temperature=0`。
- **调用工具**: 无。
- **核心逻辑**:
  ```python
  def classifier(state):
      recent = state["messages"][-3:]
      resp = deepseek.invoke(CLASSIFIER_PROMPT.format(
          history=recent, prev_intent=state.get("intent"),
          context_source=state.get("context_source")),
          response_format={"type": "json_object"})
      result = json.loads(resp.content)
      if result["confidence"] < 0.7:
          return {"intent": state.get("intent") or "forward_etl",
                  "needs_clarification": True}
      return {"intent": result["intent"], "needs_clarification": False}
  ```
- **下游节点**: 按 `intent` 分支到 `forward_etl` / `reverse_synth` / `schema_evolve`；若 `needs_clarification=True`，先走 `presenter` 输出澄清问题、等用户回复。
- **错误处理**: JSON 解析失败 → 重试 1 次；仍失败 → 关键词降级（"造数据" → reverse_synth；"加/改字段" → schema_evolve；默认 forward_etl）。

##### `forward_etl`

- **作用**: 正向 ETL 路径入口；从用户消息抽取目标/源表初步候选。
- **触发**: classifier 判定 `intent="forward_etl"`。
- **输入** (State): `messages`、`context_source`。
- **输出** (State): `target_tables`、`source_tables`、`code_type` (可选)。
- **LLM 调用**: 是 — JSON 输出 `{"target_entities":[], "source_hints":[], "code_type_hint":"spark_sql/flink_sql/java_flink/auto"}`。
- **调用工具**: `search_tables_by_keyword`。
- **核心逻辑**:
  ```python
  def forward_etl(state):
      parsed = json.loads(deepseek.invoke(EXTRACT_PROMPT.format(
          msg=state["messages"][-1].content, intent="forward_etl"),
          response_format={"type":"json_object"}).content)
      targets = [search_tables_by_keyword(k).top_table for k in parsed["target_entities"]]
      sources = [search_tables_by_keyword(k).top_table for k in parsed.get("source_hints", [])]
      hint = parsed.get("code_type_hint")
      return {"target_tables": targets, "source_tables": sources,
              "code_type": hint if hint and hint != "auto" else None}
  ```
- **下游节点**: `schema_lookup`。
- **错误处理**: 抽取失败 → 空候选下传，下游 gap_check 兜底；搜索全部低置信 → 不阻塞，由 gap_check 标记。

##### `reverse_synth`

- **作用**: 反向合成路径入口；识别目标评估对象的根表。
- **触发**: classifier 判定 `intent="reverse_synth"`。
- **输入** (State): `messages`、`context_source`。
- **输出** (State): `target_tables` (通常 1 个根表)、`row_count_hint`、`buckets_hint`；`source_tables` 留给 `pipeline_parse` 填充。
- **LLM 调用**: 是 — JSON 输出 `{"eval_target", "row_count_hint", "buckets_hint"}`。
- **调用工具**: `search_tables_by_keyword`。
- **核心逻辑**:
  ```python
  def reverse_synth(state):
      parsed = json.loads(deepseek.invoke(EXTRACT_PROMPT.format(
          msg=state["messages"][-1].content, intent="reverse_synth"),
          response_format={"type":"json_object"}).content)
      target = search_tables_by_keyword(parsed["eval_target"]).top_table
      return {"target_tables": [target], "source_tables": [],
              "row_count_hint": parsed.get("row_count_hint", 10),
              "buckets_hint": parsed.get("buckets_hint", [])}
  ```
- **下游节点**: `pipeline_parse`。
- **错误处理**: `eval_target` 无命中 → 由 gap_check 标 missing_table；提取失败 → presenter 让用户重述目标。

##### `schema_evolve`

- **作用**: 元数据演进入口；主流程（用户主动 NL 演进）或子流程（gap_proposal 自动调用）共用。
- **触发**: classifier 判定 `intent="schema_evolve"`（主）；gap_proposal 用户确认后跳入（子）。
- **输入** (State): `messages`（主）；`gaps` + `sub_flow_active=True`（子）。
- **输出** (State): `schema_diff` (待应用变更草案)。
- **LLM 调用**: 主流程 — 是，从 NL 生成 schema 变更；JSON 严格约束 `[{operation, table, field, ...}]`。子流程 — 否，复用 gap_proposal 已生成的草案。
- **调用工具**: `lookup_table_schema`。
- **核心逻辑**:
  ```python
  def schema_evolve(state):
      if state.get("sub_flow_active"):
          diff = build_diff_from_gap_draft(state)   # 子流程: 复用 gap_proposal 输出
      else:
          current = lookup_table_schema(state.get("target_tables", []))
          diff = json.loads(deepseek.invoke(SCHEMA_EVOLVE_PROMPT.format(
              user_request=state["messages"][-1].content, current_schema=current),
              response_format={"type":"json_object"}).content)
      return {"schema_diff": diff}
  ```
- **下游节点**: `schema_validate`。
- **错误处理**: LLM 输出违反 JSON Schema → 更严 prompt 重提 1 次；仍失败 → presenter "无法解析变更意图"。

##### `schema_validate`

- **作用**: 在写库前做一致性校验（重名 / 断链 / 循环依赖 / 类型兼容）。
- **触发**: `schema_evolve` 完成后。
- **输入** (State): `schema_diff`。
- **输出** (State): `validation_result` (errors / warnings / passed)。
- **LLM 调用**: 无。
- **调用工具**: `validate_change`。
- **核心逻辑**:
  ```python
  def schema_validate(state):
      diff, errors, warnings = state["schema_diff"], [], []
      for op in diff:
          if op["operation"] == "ADD_FIELD" and field_exists(op["table"], op["field"]):
              errors.append(("DUPLICATE", op))
          if op["operation"] == "DELETE_FIELD":
              ds = find_downstream(op["table"], op["field"])
              if ds: errors.append(("BREAK_DOWNSTREAM", op, ds))
      if has_cycle_after_apply(diff):
          errors.append(("CYCLE", diff))
      return {"validation_result": {"errors": errors, "warnings": warnings,
                                     "passed": len(errors) == 0}}
  ```
- **下游节点**: `passed=True` → `schema_apply`；`passed=False` → `presenter`（子流程下同时清 `sub_flow_active`）。
- **错误处理**: errors 终止本路径；warnings 不阻塞，透传 presenter 给用户提示。

##### `schema_apply`

- **作用**: 把 `schema_diff` 应用到 Neo4j，同步重写 YAML 并 git commit，回填 `Change` 节点 `commit_hash`。
- **触发**: `schema_validate.passed=True`。
- **输入** (State): `schema_diff`、`validation_result`。
- **输出** (State): `applied_changes` (含 version / commit_hash)。
- **LLM 调用**: 无。
- **调用工具**: `add_table` / `add_field` / `update_field` / `remove_field`、`sync_yaml`。
- **核心逻辑**:
  ```python
  def schema_apply(state):
      applied = []
      with neo4j_session.begin_transaction() as tx:
          for op in state["schema_diff"]:
              # CRUD 节点/边 + version+1 + 同事务内创建 (:Change {commit_hash:null}) 节点
              applied.append(dispatch_change(tx, op))
          sync_yaml(affected_tables(state["schema_diff"]))   # 同事务内 YAML 写入失败则回滚
          tx.commit()
      commit_hash = git_commit(f"schema_evolve: {summarize(state['schema_diff'])}")
      for a in applied:
          update_change_commit(a["change_id"], commit_hash)   # 回填 Change.commit_hash
      return {"applied_changes": applied}
  ```
- **下游节点**: 主流程 → `presenter`；子流程（`sub_flow_active=True` 时进入的）→ `schema_lookup`。
- **错误处理**: Neo4j 写失败 → 事务回滚；YAML 写失败 → 同事务内回滚；git commit 失败 → 库已写入但 `commit_hash=null`，由对账脚本下次启动补齐。

##### `schema_lookup`

- **作用**: 取 `target_tables` + `source_tables` 的最新 schema 到 State；子流程返回时清 `sub_flow_active`。
- **触发**: `forward_etl` 完成后；`schema_apply` 子流程完成后。
- **输入** (State): `target_tables`、`source_tables`、`sub_flow_active`。
- **输出** (State): `schemas_resolved`；子流程返回时同步 `sub_flow_active=False`。
- **LLM 调用**: 无。
- **调用工具**: `lookup_table_schema`、`lookup_lineage`（必要时回查上游）。
- **核心逻辑**:
  ```python
  def schema_lookup(state):
      schemas = lookup_table_schema(state["target_tables"] + state["source_tables"])
      out = {"schemas_resolved": schemas}
      if state.get("sub_flow_active"):
          out["sub_flow_active"] = False
      return out
  ```
- **下游节点**: 主流程 → `gap_check`；子流程返回 → 由 `sub_flow_return_point` 指定（通常 `code_generate`）。
- **错误处理**: 表不存在 → 不抛错，由 gap_check 检测；DB 异常 → `error_feedback` + presenter。

##### `pipeline_parse`

- **作用**: 反向合成专用 — 从根表回溯整条计算链路，构建上游表/字段集合。
- **触发**: `reverse_synth` 完成后。
- **输入** (State): `target_tables` (单根表)。
- **输出** (State): `source_tables` (回溯到的全部上游)、`pipeline_chain` (有序链路 + 每层表达式)。
- **LLM 调用**: 无。
- **调用工具**: `lookup_lineage`。
- **核心逻辑**:
  ```python
  def pipeline_parse(state):
      root = state["target_tables"][0]
      chain, visited, stack = [], set(), [root]
      while stack:
          t = stack.pop()
          if t in visited: continue
          visited.add(t)
          l = lookup_lineage(t, direction="up")
          chain.append({"table": t, "fields": l.fields, "upstream": l.upstream_tables})
          stack.extend(l.upstream_tables)
      return {"source_tables": list(visited - {root}),
              "pipeline_chain": list(reversed(chain))}   # ODS → EVAL 顺序
  ```
- **下游节点**: `gap_check`。
- **错误处理**: 链路断链（上游表不存在）→ 标 missing_table 传 gap_check。

##### `gap_check`

- **作用**: 检测用户需求实体与现有元数据的缺口，决定是否进入 gap_proposal 补齐子流程。
- **触发**: `schema_lookup`（正向）或 `pipeline_parse`（反向）后。
- **输入** (State): `messages`、`target_tables`、`source_tables`、`pipeline_chain` (反向)。
- **输出** (State): `gaps`、`has_gaps`。
- **LLM 调用**: 是 — `extract_required_entities` 内部调用；JSON 输出 `[{"keyword", "field_specified", "field"}]`。
- **调用工具**: `search_tables_by_keyword`、`check_gaps`。
- **核心逻辑**:
  ```python
  def gap_check(state):
      """检测用户需求与现有元数据之间的缺口"""
      required = extract_required_entities(state["messages"][-1])
      gaps = []
      for entity in required:
          match = search_tables_by_keyword(entity.keyword)
          if match.top_score < 0.6:
              gaps.append({"type": "missing_table", "keyword": entity.keyword,
                           "suggestion": f"建议新建表 {entity.pinyin}_metrics"})
          elif entity.field_specified and not field_exists(entity.field, match.top_table):
              gaps.append({"type": "missing_field", "keyword": entity.field,
                           "table": match.top_table,
                           "suggestion": f"在 {match.top_table} 中新增字段 {entity.field}"})
      return {"gaps": gaps, "has_gaps": len(gaps) > 0}
  ```
  > 阈值 0.6 用于缺口检测（保守判定，宁多勿漏），不同于语义检索 RRF 置信阈值 0.15（4.6.5 节）。
- **下游节点**: `has_gaps=False` → `code_generate`；`has_gaps=True` → `gap_proposal`。
- **错误处理**: 抽取失败 → 默认 `has_gaps=False`（让 code_generate 尝试，由 dry_run 失败后 Agent 层重试兜底）。

##### `gap_proposal`

- **作用**: 根据 gaps 生成补齐草案（新表/新字段），先渲染给用户确认。
- **触发**: `gap_check` 返回 `has_gaps=True`。
- **输入** (State): `gaps`、`messages`。
- **输出** (State): `schema_diff`、`sub_flow_active=True`、`sub_flow_return_point="code_generate"`、`presenter_payload`。
- **LLM 调用**: 是 — 草案生成；JSON 含 `[{operation, table, layer, storage_type, fields:[...]}]`，含合理的层级 / 存储推断。
- **调用工具**: `propose_gap_fix`。
- **核心逻辑**:
  ```python
  def gap_proposal(state):
      draft = json.loads(deepseek.invoke(PROPOSE_PROMPT.format(
          gaps=state["gaps"], user_request=state["messages"][-1].content),
          response_format={"type":"json_object"}).content)
      return {"schema_diff": draft,
              "sub_flow_active": True,
              "sub_flow_return_point": "code_generate",
              "presenter_payload": {"type": "gap_proposal_card",
                                    "draft": draft, "gaps": state["gaps"]}}
  ```
- **下游节点**: 先 `presenter`（渲染卡片等用户选择）；用户 [确认并继续] → `schema_evolve` 子流程；[我自己定义] / [跳过] → `code_generate`。
- **错误处理**: 草案违反约束 → 更严 prompt 重提 1 次；仍失败 → presenter "无法自动补齐，请手动定义"。

##### `code_generate`

- **作用**: 根据已确认的 schema 和用户意图生成 Spark SQL / Flink SQL / Java Flink 代码。
- **触发**: `schema_lookup` 完成后（含 gap 子流程返回）；`dry_run` 失败时 Agent 层重试。
- **输入** (State): `intent`、`target_tables`、`source_tables`、`messages`、`error_feedback` (重试)、`code_type`。
- **输出** (State): `generated_code`、`code_type`、`iteration_count` (+1)。
- **LLM 调用**: 是 — prompt 含 schema、意图、用户原话、目标 code_type、上一次 `error_feedback`（若有）；输出代码块 + 解释，正则提取代码部分。
- **调用工具**: `lookup_table_schema`（拿最新 schema）。
- **核心逻辑**:
  ```python
  def code_generate(state):
      schema = lookup_table_schema(state["target_tables"] + state["source_tables"])
      code_type = state.get("code_type") or infer_code_type(state)
      resp = deepseek.invoke(CODE_GEN_PROMPT.format(
          schema=schema, intent=state["intent"],
          user_request=state["messages"][-1].content,
          code_type=code_type,
          error_feedback=state.get("error_feedback")))
      code = extract_code_block(resp.content, lang=code_type_to_lang(code_type))
      return {"generated_code": code, "code_type": code_type,
              "iteration_count": state.get("iteration_count", 0) + 1}
  ```
- **下游节点**: `dry_run`。
- **错误处理**: LLM 输出无代码块 → 更严 prompt 重提一次；仍失败 → presenter 返回 fatal；`iteration_count ≥ 3` → 终止 Agent 层重试。

##### `dry_run`

- **作用**: 把 `generated_code` 提交沙箱执行，回填结果或错误反馈。
- **触发**: `code_generate` 完成后。
- **输入** (State): `generated_code`、`code_type`。
- **输出** (State): `dry_run_result`；失败时 `error_feedback`。
- **LLM 调用**: 无。
- **调用工具**: `dry_run_spark_sql` / `dry_run_flink_sql` / `dry_run_java_flink`（按 `code_type` 分派）。
- **核心逻辑**:
  ```python
  def dry_run(state):
      tool = {"spark_sql": dry_run_spark_sql,
              "flink_sql": dry_run_flink_sql,
              "java_flink": dry_run_java_flink}[state["code_type"]]
      result = tool(state["generated_code"])
      if not result.success:
          return {"dry_run_result": result, "error_feedback": result.error_log[:2000]}
      return {"dry_run_result": result, "error_feedback": None}
  ```
- **下游节点**: 成功 → `presenter`；失败 + `iteration_count<3` → `code_generate`（Agent 层重试）；失败 + `iteration_count≥3` → `presenter`（带失败标记）。
- **错误处理**: 沙箱基础设施异常（YARN/HDFS 不可达）→ 不计入 Agent 层重试，直接 presenter 标 "基础设施异常"。

##### `presenter`

- **作用**: 终止节点 — 将 State 汇总成 UI 载荷并通过 SSE 推送，结束本轮 LangGraph 执行。
- **触发**: dry_run 成功；多种异常路径；gap_proposal 后等用户确认；classifier `needs_clarification=True`。
- **输入** (State): `intent`、`generated_code`、`code_type`、`dry_run_result`、`schema_diff`、`gaps`、`error_feedback`、`iteration_count`、`presenter_payload`。
- **输出**: 不再写 State；通过 SSE 推送 `final_message`。
- **LLM 调用**: 是（可选）— 把技术结果转对话语气；`temperature=0.3`。
- **调用工具**: 无。
- **核心逻辑**:
  ```python
  def presenter(state):
      payload = build_payload_by_intent_and_state(state)
      # type: code_card / dry_run_preview / schema_diff_card / gap_proposal_card / clarification / error
      sse_emit(payload)
      return {"final_message": payload["summary"]}
  ```
- **下游节点**: END。
- **错误处理**: 自身出错也要发 SSE — 至少 "流程异常: {brief}"，不让对话挂死。

### 4.2 Agent State

```python
class AgentState(TypedDict, total=False):
    # —— classifier / 对话基础 ——
    messages: Annotated[list, add_messages]   # 对话历史
    intent: str                                # "forward_etl" | "reverse_synth" | "schema_evolve"
    context_source: str                        # 上下文来源: "metadata" | "lineage" | "pipeline" | None
    needs_clarification: bool                  # classifier 低置信度时为 True, 走 presenter 澄清

    # —— forward_etl / schema_lookup ——
    target_tables: list[str]
    source_tables: list[str]
    schemas_resolved: dict                     # schema_lookup 取回的 {table: schema} 映射

    # —— reverse_synth / pipeline_parse ——
    row_count_hint: int                        # 反向合成期望行数 (默认 10)
    buckets_hint: list[dict]                   # 反向合成分档提示 (如 [{"label":"优","range":[80,100]}])
    pipeline_chain: list[dict]                 # 回溯链路: [{"table","fields","upstream"}], ODS→EVAL 顺序

    # —— code_generate / dry_run ——
    generated_code: str
    code_type: str                             # "spark_sql" | "flink_sql" | "java_flink"
    dry_run_result: dict                       # {success, preview_row, error_log}
    error_feedback: str                        # 上一轮失败反馈, 重试时传入 code_generate
    iteration_count: int                       # Agent 层重试计数, 含首次

    # —— schema_evolve / validate / apply ——
    schema_diff: dict                          # 待应用变更草案
    validation_result: dict                    # {errors, warnings, passed}
    applied_changes: list[dict]                # schema_apply 后落库的变更条目 (含 version / commit_hash)

    # —— gap_check / gap_proposal 子流程 ——
    gaps: list[dict]                           # 缺失对象列表
    has_gaps: bool                             # gap_check 结论
    resolved_gaps: dict                        # 已补齐的映射 {keyword: table_name}
    sub_flow_active: bool                      # 是否正在子流程中
    sub_flow_return_point: str                 # 子流程完成后回到哪个节点

    # —— presenter ——
    presenter_payload: dict                    # {type, ...} 给 UI 的预构建载荷
    final_message: str                         # presenter 输出的对话总结文案
```

> `total=False` 表示所有字段可选 — 不同路径只写自己关心的子集，LangGraph 自动 merge。

### 4.3 Tools (Agent 可调用)

| 工具 | 功能 | 路径 |
|------|------|------|
| `lookup_table_schema` | 查表/字段元数据 | 所有 |
| `lookup_lineage` | 查字段血缘路径 | 所有 |
| `search_tables_by_keyword` | 语义搜索表 (业务关键词→表/字段匹配) | 所有 |
| `check_gaps` | 检测用户需求实体与现有元数据的缺口 | forward_etl, reverse_synth |
| `propose_gap_fix` | 生成缺失表/字段的补齐建议 | forward_etl, reverse_synth |
| `generate_fake_data` | 反向合成小批量数据 | reverse_synth |
| `validate_change` | 变更一致性检查 (重名/断链/循环依赖) | schema_evolve |
| `add_table / add_field / update_field / remove_field` | 元数据变更 | schema_evolve |
| `sync_yaml` | Neo4j 变更后同步重写 YAML 文件 | schema_evolve |
| `dry_run_spark_sql` | Spark SQL E2E + HDFS 回读 | forward_etl |
| `dry_run_flink_sql` | Flink SQL E2E + HDFS 回读 | forward_etl |
| `dry_run_java_flink` | Java Flink E2E + HDFS 回读 | forward_etl |

> - `lookup_table_schema` / `lookup_lineage` 是 Agent 内部工具，直接读 Neo4j (Cypher) — 与 HTTP `/api/tables`、`/api/lineage` 共享同一个 service 函数，但不经过 HTTP。
> - `dry_run_spark_sql / dry_run_flink_sql / dry_run_java_flink` 三个工具均是 thin wrapper，统一委派给 `SandboxController.execute(code, code_type)`（§5.4）。分三个工具仅为让 Agent 通过工具名表达执行意图。

### 4.4 DeepSeek 集成

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

LangChain `ChatOpenAI` 指定 `base_url` + `api_key` 即可。

### 4.5 自动重试（双层）

重试分两层，互补不重叠：

| 层 | 触发场景 | 重试上限 | 处理方式 |
|----|---------|---------|---------|
| 沙箱层（§5.4 `execute_with_retry`） | 编译失败 / YARN 平台异常 | 2 轮 | 解析 maven / YARN 日志 → LLM 修正代码 → 重新提交 |
| Agent 层（本节） | 沙箱层耗尽后仍失败 / 业务逻辑错误 / SQL 语义错误 | 3 轮 | error_feedback 写入 State，`code_generate` 节点重新生成代码 |

Agent 层 `iteration_count` 计入包括首次执行在内的总轮次（首次 + 最多 2 次重试 = 3 轮）。沙箱层重试在单次 dry-run 内部完成，不计入 Agent 层 `iteration_count`。

### 4.6 语义检索技术实现

`search_tables_by_keyword` 是 Agent 三条路径的入口工具。用户只讲业务指标（"小区每小时的覆盖强度"），不知道 `dws_cell_hourly` / `avg_rsrp`。该工具将业务语义映射到表/字段。

#### 4.6.1 检索空间

Neo4j 中 10 张表 + ~70 个字段，每条生成一个索引文本：

```python
# 表级
table_doc = {
    "id": "table:dws_cell_hourly",
    "type": "table",
    "text": "dws_cell_hourly 小区小时粒度汇总指标 cell_id 小区标识 "
            "hour_bucket 小时窗口起点 avg_rsrp 小区小时平均RSRP覆盖强度 "
            "avg_sinr 小区小时平均SINR信噪比 total_sessions 会话总数 "
            "drop_rate 掉话率 avg_throughput 平均吞吐量Mbps "
            "ho_success_rate 切换成功率",
    "metadata": {
        "table_name": "dws_cell_hourly",
        "layer": "DWS",
        "storage_type": "HIVE",
        "version": 1
    }
}

# 字段级
field_doc = {
    "id": "field:dws_cell_hourly.avg_rsrp",
    "type": "field",
    "text": "avg_rsrp DOUBLE 小区小时平均RSRP覆盖强度dBm "
            "表达式 AVG(dwd_session_qos.avg_rsrp)",
    "metadata": {
        "table_name": "dws_cell_hourly",
        "field_name": "avg_rsrp",
        "data_type": "DOUBLE",
        "version": 1
    }
}
```

#### 4.6.2 组件选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 中文分词 | jieba | 轻量、纯 Python、RNO 术语词典可自定义 |
| Embedding 模型 | `BAAI/bge-small-zh-v1.5` | 24MB、512 维、MIT 开源、CLS pooling、批量编码 ~5ms/条 (CPU) |
| 关键词检索 | BM25 (rank-bm25) | 对 RSRP/SINR/cell_id 等技术术语精确匹配，与分词互补 |
| 向量存储 | ChromaDB (persistent) | Python 原生、本地文件持久化（ChromaDB 内部使用 SQLite，与本项目元数据存储 Neo4j 无关）、内置 metadata filter、upsert 增量更新 |
| 精排兜底 | DeepSeek Chat | 口语化/模糊表达时做 LLM rerank |

#### 4.6.3 文本预处理

```python
import jieba

# 自定义技术术语词典，保护不被切分
jieba.add_word("覆盖强度", freq=100)
jieba.add_word("信噪比", freq=100)
jieba.add_word("掉话率", freq=100)
jieba.add_word("切换成功率", freq=100)
jieba.add_word("RSRP", freq=100)
jieba.add_word("SINR", freq=100)

def tokenize(text: str) -> list[str]:
    words = jieba.lcut(text)
    return [w.strip().lower() for w in words if w.strip()]
```

#### 4.6.4 初始化与增量同步

```
FastAPI 启动时:
  1. 加载 bge-small-zh-v1.5 到内存 (24MB, ~1s)
  2. ChromaDB PersistentClient 连接 ./data/chroma/
  3. 如果 Chroma 为空 → 从 Neo4j 加载元数据 (Cypher: MATCH (t:Table)-[:HAS_FIELD]->(f)) → 构建索引文本
     → 向量化 → 写入 Chroma → 构建 BM25 倒排
  4. 如果 Chroma 已有 → 对比 Chroma index_version 与 Neo4j MAX(f.version)
     → 仅 upsert 变更的 docs → 重建 BM25 (增量, <1ms)
```

```python
class HybridSearcher:
    def __init__(self, chroma_path: str = "./data/chroma"):
        self.encoder = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="metadata_index",
            metadata={"hnsw:space": "cosine"}
        )
        self.bm25 = None

    def build_index(self, docs: list[dict]):
        texts = [d["text"] for d in docs]
        embeddings = self.encoder.encode(texts, normalize_embeddings=True).tolist()
        self.collection.upsert(
            ids=[d["id"] for d in docs],
            embeddings=embeddings,
            metadatas=[d["metadata"] for d in docs],
            documents=texts
        )
        from rank_bm25 import BM25Okapi
        self.bm25_docs = docs
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])
        self.collection.modify(metadata={"index_version": self._db_version()})
```

异常处理:

- bge-small-zh-v1.5 模型下载失败：FastAPI 启动时 `SentenceTransformer` 加载失败 → 降级为纯 BM25 模式 + 日志告警，语义搜索仍可用（仅 Dense 向量检索不可用）
- ChromaDB 数据损坏：`PersistentClient` 连接失败 → 自动重建（删除 `./data/chroma/` → 从 Neo4j 全量重建索引）
- 内存压力：bge 模型 24MB + ChromaDB 持久化文件 < 10MB (80 docs × 512维)，总计 < 50MB，无需特殊处理

#### 4.6.5 混合检索流程

```
用户输入: "每个小区的每小时信号覆盖强度"
        │
        ├─→ jieba 分词: ["每个","小区","每小时","信号","覆盖强度"]
        │   → BM25 Okapi 倒排检索 → Top 10
        │
        ├─→ bge-small-zh 编码 → 512维归一化向量
        │   → ChromaDB cosine 检索 → Top 10
        │
        ▼
    RRF (Reciprocal Rank Fusion):
      score(doc) = Σ 1/(k + rank_i)
      k = 60 (阻尼常数，防止 Top-1 过主导)

      融合后 → Top 10
        │
        ├─→ 置信度判断:
        │     Top-1 RRF score > 0.15  → 直接返回 (约 80% 查询)
        │     否则                     → LLM rerank
        │
        ▼
    返回: [{"table": "dws_cell_hourly", "score": 0.87, "fields": [...], "match_type": "hybrid"}, ...]
```

```python
def search(self, query: str, k: int = 10,
           use_rerank: bool = True) -> list[dict]:
    # 1. BM25
    bm25_scores = self.bm25.get_scores(tokenize(query))
    bm25_ranked = sorted(zip(self.bm25_docs, bm25_scores),
                         key=lambda x: -x[1])

    # 2. Dense (ChromaDB)
    query_vec = self.encoder.encode(
        [query], normalize_embeddings=True
    ).tolist()[0]
    dense = self.collection.query(
        query_embeddings=[query_vec],
        n_results=k,
        include=["metadatas", "documents", "distances"]
    )

    # 3. RRF 融合
    fused = self._rrf_fuse(bm25_ranked, dense, k=k)

    # 4. LLM rerank (仅低置信度触发)
    if use_rerank and fused[0][1] < self.RERANK_THRESHOLD:
        fused = self._llm_rerank(query, fused)

    return [{"doc": d, "score": s,
             "table": d["metadata"]["table_name"]}
            for d, s in fused]
```

#### 4.6.6 RRF 融合公式

```python
def _rrf_fuse(self, bm25_ranked, dense_result, k=60, top_k=10):
    scores = {}
    for rank, (doc, _) in enumerate(bm25_ranked):
        scores[doc["id"]] = scores.get(doc["id"], 0) + 1.0 / (k + rank + 1)

    for rank, doc_id in enumerate(dense_result["ids"][0]):
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    doc_map = {d["id"]: d for d in self.bm25_docs}
    return [(doc_map[id_], scoring) for id_, scoring in ranked[:top_k]]
```

#### 4.6.7 LLM Rerank (兜底)

仅在 RRF Top-1 score < 0.15 时触发，约占 20% 查询：

```python
RERANK_PROMPT = """你是无线网络数据专家。用户用自然语言描述了业务需求，
请从以下候选元数据对象中选出最匹配的表和字段。

用户需求: {user_query}

候选对象 (JSON):
{candidates_json}

返回严格的 JSON 格式 (不要 Markdown 包裹):
{{
  "top_table": {{"name": "...", "score": 0.95, "reason": "..."}},
  "top_fields": [{{"name": "...", "table": "...", "score": 0.88, "reason": "..."}}],
  "alternative_tables": [{{"name": "...", "score": 0.72, "reason": "..."}}]
}}
"""

def _llm_rerank(self, query: str, candidates) -> list:
    """用 DeepSeek Chat 做最后一次精排"""
    cand_json = json.dumps([{
        "name": d["metadata"]["table_name"],
        "type": d["type"],
        "description": d["text"][:200]
    } for d, _ in candidates[:10]], ensure_ascii=False)

    resp = self.deepseek_client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content":
                   RERANK_PROMPT.format(user_query=query,
                                        candidates_json=cand_json)}],
        temperature=0,
        response_format={"type": "json_object"}
    )
    return self._parse_rerank_result(resp, candidates)
```

#### 4.6.8 延时预算

| 阶段 | 耗时 | 占比 |
|------|------|------|
| jieba 分词 | ~1ms | — |
| BM25 检索 | ~2ms | — |
| bge-small 编码 (CPU) | ~5ms | — |
| ChromaDB query | ~1ms | — |
| RRF 融合 | <1ms | — |
| **小计 (无 LLM)** | **~10ms** | 80% 查询 |
| LLM rerank (触发时) | ~500-800ms | 20% 查询 |

### 4.7 语义检索 Benchmark

#### 4.7.1 测试集构建

从元数据 YAML 自动生成 60 条 queries，覆盖 3 种构造方式 + 3 个难度：

```yaml
# benchmark_queries.yaml

# 类型 A: 规则生成 (30条) — 从 field.description 做同义词替换+语序变化
- id: Q001
  query: "小区小时粒度的平均覆盖强度"
  expected_table: "dws_cell_hourly"
  expected_fields: ["avg_rsrp"]
  difficulty: easy
- id: Q002
  query: "每个基站每小时的掉话比例"
  expected_table: "dws_cell_hourly"
  expected_fields: ["drop_rate"]
  difficulty: medium
- id: Q003
  query: "用户打电话时从一个塔切到另一个塔的成功率"
  expected_table: "dwd_ho_event"
  expected_fields: ["ho_result"]
  difficulty: hard   # 口语化: 塔→cell, 打电话→会话, 切→handover

# 类型 B: LLM 生成 (20条) — 给 DeepSeek 元数据，模拟不同角色提问
- id: Q031
  query: "帮我看看最近一段时间信号质量差的用户都有哪些"
  expected_table: "dwd_session_qos"
  expected_fields: ["avg_sinr", "avg_rsrp"]
  difficulty: medium

# 类型 C: 对抗样本 (10条) — 故意模糊/歧义/跨域
- id: Q051
  query: "网络状况怎么样"
  expected_table: "eval_net_health"
  expected_fields: ["health_index"]
  difficulty: hard   # 极度模糊
```

#### 4.7.2 评估指标

```python
@dataclass
class SearchBenchmark:
    # 表级检索
    table_recall_at_1: float    # Top-1 命中率
    table_recall_at_3: float    # Top-3 出现率
    table_mrr: float            # 平均倒数排名  Σ(1/rank) / N

    # 字段级检索
    field_recall_at_3: float
    field_ndcg_at_5: float      # 含多目标字段时

    # 效率
    avg_latency_ms: float
    p99_latency_ms: float

    # 分层
    by_difficulty: dict         # {easy: {}, medium: {}, hard: {}}
```

#### 4.7.3 目标值

| 指标 | 目标 |
|------|------|
| Table Recall@1 | > 0.85 |
| Table Recall@3 | > 0.95 |
| Table MRR | > 0.90 |
| Field Recall@3 | > 0.80 |
| Avg latency (无 LLM) | < 20ms |
| Avg latency (含 LLM rerank) | < 1s |
| Hard Recall@1 | > 0.65 |

#### 4.7.4 CI 门禁与增量回归

```
scripts/benchmark_semantic_search.py

冷启动:
  $ python scripts/benchmark_semantic_search.py --queries benchmark_queries.yaml
  → 输出完整指标表 + 每条 query 的检索链路日志
  → CI: 核心指标不得低于目标的 90%

增量 (每次 schema_evolve 后):
  $ python scripts/benchmark_semantic_search.py --mode incremental
  → 自动生成 5 条针对新增对象的 queries
  → 验证: 新对象可被检索 + 旧对象不受影响 (无回归)
  → 回归检测: 重新跑全量 60 条，对比上次 score 差异
```

---

## 5. 沙箱

### 5.1 统一模型

三种代码类型全部: Java 骨架包装 → Maven 编译 → YARN 提交 → HDFS 结果回读 → 返回 1 行

### 5.2 骨架模板

```bash
templates/
├── spark-sql/
│   ├── pom.xml
│   └── src/main/java/SandboxSparkJob.java   # ${user_sql} 注入点, sink → hdfs:///tmp/sandbox/{uuid}/
├── flink-sql/
│   ├── pom.xml
│   └── src/main/java/SandboxFlinkSQLJob.java # ${user_sql} 注入点 (替换 SQL 字符串)，sink → hdfs:///tmp/sandbox/{uuid}/
└── flink-java/
    ├── pom.xml
    └── src/main/java/                        # 整个 src/ 目录替换，约定 sink 路径 hdfs:///tmp/sandbox/{uuid}/
```

### 5.3 提交方式

| 路径 | 编译 | 提交方式 | 结果读回 |
|------|------|----------|----------|
| Spark SQL | `mvn package` | `subprocess`: `spark-submit --master yarn --deploy-mode cluster jar` | `spark.read.json(hdfs://tmp/sandbox/{uuid})` → 1 行 |
| Flink SQL | `mvn package` | `subprocess`: `flink run -m yarn-cluster jar` | 同上 |
| Java Flink | `mvn package` | `subprocess`: `flink run -m yarn-cluster jar` | 同上 |

### 5.4 控制器封装

```python
class YarnSandbox:
    async def compile(self, code: str, code_type: str) -> CompileResult
    async def submit_spark(self, jar_hdfs_path: str) -> str      # → applicationId (subprocess: spark-submit)
    async def submit_flink(self, jar_hdfs_path: str) -> str      # → applicationId (subprocess: flink run)
    async def wait_complete(self, app_id: str, engine: str) -> bool   # 轮询 YARN RM REST :8088
    async def read_result(self, uuid: str) -> dict               # → 1 row

class SandboxController:
    async def execute(self, code: str, code_type: str) -> DryRunResult:
        1. sandbox_dir = /tmp/sandbox/{uuid}
        2. copy_template + inject_code
        3. maven_compile()
        4. upload JAR to HDFS
        5. submit_and_wait()
        6. read_result() → 1 row
        7. cleanup sandbox_dir

    async def execute_with_retry(self, code: str, code_type: str,
                                 max_retries: int = 2) -> DryRunResult:
        """沙箱级自动重试：针对编译失败和 YARN 执行失败，最多 2 轮。
        编译失败: 解析 maven 错误 → 提取行号/错误类型 → 修正 → 重试
        执行失败: 解析 YARN 日志 → 提取异常 → 修正 → 重试
        与 Agent 层重试 (4.5 节) 分层互补：沙箱层解决编译/平台问题，
        Agent 层解决业务逻辑/SQL 语义问题。
        """
```

### 5.5 资源限制

| 项 | 限制 |
|----|------|
| 总超时 | 60s |
| Spark job | 30s |
| Flink job | 45s |
| Java 编译 | 20s |
| 返回行数 | 1 行 |
| Spark 并行度 | local[2] |
| 临时目录 | `/tmp/sandbox/{uuid}` → 执行完清理 |

---

## 6. Web UI

### 6.1 技术栈

| 层 | 选型 |
|----|------|
| 框架 | React 18 + TypeScript |
| 构建 | Vite |
| UI 库 | Ant Design |
| 图可视化 | AntV X6 (血缘工作台) + AntV G6 (Pipeline DAG) |
| 代码高亮 | Monaco Editor (readonly + 可编辑切换) |
| 图表 | @antv/g2 (柱状图等) |
| SSE | fetch + ReadableStream |
| 状态 | React Query (服务端) + Zustand (客户端) |

### 6.2 页面 & 路由

| 路由 | 页面 | 核心功能 |
|------|------|----------|
| `/metadata` | 元数据管理 | 分类树/标签导航 + 表浏览/搜索/CRUD + 字段编辑 + YAML 导出 |
| `/metadata/lineage` | 血缘工作台 | 表级血缘主图 + 字段展开血缘 + 结构化边编辑 + SQL 生成/导入 + 跳转 /chat |
| `/chat` | NL 对话 | 对话面板 + 代码卡片 + dry-run 预览 |
| `/pipeline` | Pipeline 可视化 | 正向 ETL DAG + 反向合成链路，只读消费血缘结果 |
| `/schema-evolution` | 演化历史 | 变更时间线 + 版本 diff |
| `/health` | 健康检查 | Docker 组件连通性状态面板 (30s 自动刷新) |

### 6.3 元数据管理界面 (/metadata)

#### 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  [搜索框: 表名/字段/描述...]          [+ 新建表]  [导出 YAML]  │
├──────────────────────┬───────────────────────────────────────┤
│ 左侧面板 (320px)      │ 右侧面板                               │
│                      │                                       │
│ 分层过滤:             │ ┌── 表信息卡片 ──────────────────┐    │
│  ● L1 接入层 (2)     │ │ dws_cell_hourly                │    │
│  ○ L2 明细层 (2)     │ │ 层: DWS │ 存储: HIVE           │    │
│  ○ L3 汇总层 (2)     │ │ 分区: hour_bucket              │    │
│  ○ L4 宽表层 (2)     │ │ 描述: 小区小时粒度汇总指标...    │    │
│  ○ L5 评估层 (2)     │ │ [编辑] [删除] [查看血缘]        │    │
│                      │ └────────────────────────────────┘    │
│ 表列表:               │                                       │
│ ┌──────────────────┐ │ ┌── 字段列表 (可搜索) ───────────┐    │
│ │★ dws_cell_hourly │ │ │ [搜索字段...]                  │    │
│ │  小区小时汇总      │ │ ├──────┬─────┬────┬────────────┤    │
│ │  7字段·DWS·HIVE  │ │ │ 字段  │ 类型 │可空│ 表达式      │    │
│ │                  │ │ │cell_id│STRING│ ✗ │ (原始)      │    │
│ │ dwd_session_qos  │ │ │hour   │TIMEST│ ✗ │ TRUNC()    │    │
│ │  会话QoS明细      │ │ │avg_   │DOUBLE│ ✓ │ AVG()      │    │
│ │  8字段·DWD·HIVE  │ │ │rsrp   │      │   │            │    │
│ │                  │ │ │avg_   │DOUBLE│ ✓ │ AVG()      │    │
│ │ ods_ue_signal    │ │ │sinr   │      │   │            │    │
│ │  UE信号采集       │ │ │...    │...   │...│ ...        │    │
│ │  6字段·ODS·Kafka │ │ └──────┴─────┴────┴────────────┘    │
│ └──────────────────┘ │ [+ 新建字段]                          │
│                      │                                       │
│ [hover 表行]: 描述    │ [hover 字段行]: 上游引用 tooltip       │
│ [点击表行]: 显示详情  │ [点击字段行]: 打开编辑抽屉             │
└──────────────────────┴───────────────────────────────────────┘
```

#### 功能详单

| 功能 | 入口 | 说明 |
|------|------|------|
| 分层浏览 | 左侧 radio button | 单选层过滤表列表 |
| 搜索表 | 顶部搜索框 | 模糊匹配表名/字段名/描述 |
| 表详情 | 点击表行 | 右侧面板显示表信息卡片 + 字段列表 |
| 字段详情+编辑 | 点击字段行 | 右侧滑出抽屉，含 Monaco 表达式编辑器 |
| 上游 tooltip | hover 字段行 | 浮层显示该字段依赖的上游字段和表达式 |
| 新建表 | 顶部 [+ 新建表] | 弹窗: 表名/层/存储/分区/描述 + 字段定义列表 |
| 编辑表 | 表卡片 [编辑] | 修改层/存储/描述 |
| 删除表 | 表卡片 [删除] | 二次确认 + 下游影响检查 |
| 新建字段 | 字段列表 [+ 新建字段] | 行内或弹窗添加 |
| 删除字段 | 字段行 ✕ | 下游依赖检查 → 警告或拒绝 |
| 导出 YAML | 顶部 [导出 YAML] | 全量或按选定表导出到 metadata-yaml/ |
| YAML 预览 | 表卡片 [预览 YAML] | 只读弹窗展示当前表 YAML 内容 (Monaco 语法高亮)，不落盘 |
| 查看血缘 | 表卡片 [查看血缘] | 跳转到 `/metadata/lineage?table=xxx` |
| 创建下游表 | 表卡片 [创建下游表] | 打开新建表弹窗，预填上游引用 |

#### 分类与标签导航管理

`/metadata` 左侧导航从单一分层过滤升级为“主分类树 + 标签筛选”：

- 分类树单选：展示 `环境/设备/网络/用户/业务/源数据` 六个大分类及其小分类，节点显示表数量；点击小分类后按该分类过滤表列表。
- 标签多选：标签平铺展示，可按 `MetaTagGroup` 折叠；支持 `tag_match=any|all` 切换，默认 `any`。
- 搜索组合：顶部搜索、分类、标签、layer/storage 过滤条件同时生效。
- 未归类治理：历史无分类表进入虚拟节点“未归类”；保存表编辑时必须选择真实叶子分类。
- 表列表展示：表卡片显示主分类路径和标签 chips，便于确认当前纳管状态。

左侧顶部提供“管理分类/标签”按钮，打开抽屉：

| Tab | 能力 | 边界 |
|-----|------|------|
| 分类 | 新增子分类、改名、移动、排序、停用 | 内置大分类不允许硬删除；允许改名、排序、停用；小分类可移动到其他大类 |
| 标签 | 新增标签、改名、排序、停用、调整分组 | 标签平铺，不做标签树；停用标签默认不出现在普通筛选中 |
| 标签分组 | 新增/改名/排序/停用分组 | 分组只影响展示，不改变标签过滤语义 |

表详情或表编辑抽屉新增“主分类路径 + 标签”区：

- 主分类路径使用树选择器，只能选择启用状态的叶子分类。
- 标签使用多选器，可选择已有标签；新建标签走管理抽屉，避免表编辑时产生无治理的临时标签。
- 保存后调用 `PUT /api/tables/:id/classification`，成功后刷新左侧计数、表列表和表详情。

#### 新建/编辑表弹窗

```
┌── 新建表 ──────────────────────────────────┐
│                                              │
│  表名:  [ods_core_gnb_load        ]          │
│  层级:  [ODS ▼]  [1]                        │
│  存储:  [Kafka ▼]                            │
│  分区键: [timestamp          ] [+ 添加]       │
│  描述:  [基站 CPU/内存/负载 原始采集数据  ]    │
│                                              │
│  ── 字段定义 ────────────────────────        │
│  ┌────┬──────┬──────┬──────────────┐        │
│  │字段 │ 类型   │ 可空  │ 表达式/描述    │        │
│  ├────┼──────┼──────┼──────────────┤        │
│  │gnb_id│STRING │ ✗   │ 基站ID        │ ✕     │
│  │cpu   │DOUBLE │ ✓   │ CPU使用率(%)   │ ✕     │
│  │mem   │DOUBLE │ ✓   │ 内存使用率(%)   │ ✕     │
│  │+ 添加字段                               │
│  └────┴──────┴──────┴──────────────┘        │
│                                              │
│  [保存]  [保存并导出 YAML]  [取消]               │
└──────────────────────────────────────────────┘
```

- [保存]：仅写入 Neo4j（运行时立即可用）
- [保存并导出 YAML]：写入 Neo4j + 同步导出对应 YAML 文件到 `metadata-yaml/` 目录 + git commit

#### 字段编辑抽屉 (右侧滑出)

```
┌── 编辑字段: avg_rsrp ───────────────────────┐
│                                               │
│  字段名:  [avg_rsrp                 ]          │
│  类型:    [DOUBLE ▼]                          │
│  可空:    [✓]                                 │
│  描述:    [小区小时平均 RSRP 覆盖强度  ]        │
│                                               │
│  ── 计算逻辑 ────────────────                 │
│  表达式:                                       │
│  ┌──────────────────────────────────────┐     │
│  │ AVG(dwd_session_qos.avg_rsrp)         │     │
│  │                              Monaco   │     │
│  └──────────────────────────────────────┘     │
│                                               │
│  ── 上游引用 ────────────────                  │
│  ┌─────────────┬───────────────┐              │
│  │ 源表          │ 源字段         │    [+ 添加]  │
│  ├─────────────┼───────────────┤              │
│  │dwd_session  │ avg_rsrp      │    ✕         │
│  │_qos         │               │              │
│  └─────────────┴───────────────┘              │
│                                               │
│  _变更将自动更新血缘图_                         │
│                                               │
│               [保存]   [取消]                   │
└───────────────────────────────────────────────┘
```

### 6.4 血缘工作台界面 (/metadata/lineage)

血缘页采用“表级主图 + 字段按需展开 + 右侧编辑/SQL 面板”。默认先呈现表级血缘，避免字段级边过早铺满画布；用户展开表节点后，再在同一个节点内按字段行显示字段级血缘。

血缘工作台的中间画布使用 AntV X6，而不是复用 `/pipeline` 的 G6 DAG。X6 负责可编辑图工作台能力：表节点、字段端口、曲线边、字段级虚线边、边 hover/click、拖动端点重连和画布导航。左侧控制面板、右侧边编辑器、SQL 预览和 SQL 导入抽屉继续复用现有 React/Ant Design 组件。

#### 页面布局

```
┌────────────── 控制面板 ──────────────┬──────────────────── 血缘画布 ────────────────────┬──────────── 详情 / SQL ────────────┐
│ 目标表: [dws_cell_hourly      🔍]    │                                                      │ 当前表: dws_cell_hourly             │
│                                      │     ┌──────────────────┐      ┌──────────────────┐ │ 表级概览 / 选中边详情              │
│ [x] 前向  [x] 后向                   │     │ ods_ue_signal   + │~~~▶ │ dwd_session_qos + │ │                                      │
│ 展开层级: [1 -- 5]                  │     └──────────────────┘      └──────────────────┘ │ 计算类型: [AGGREGATE ▼]             │
│                                      │                 ╲                    ╲             │ 参数: function=AVG, group_by=...     │
│ [导入 SQL] [新建血缘边] [用 NL 修改]  │                  ╲                    ╲            │ 表达式: AVG(rsrp)                   │
│                                      │                   ╲                    ▼           │ [保存] [删除] [用 NL 修改]          │
│                                      │                ┌────────────────────────────┐       │                                      │
│                                      │                │ dws_cell_hourly       -     │       │ 生成 SQL 预览                       │
│ 图例:                                │                │ avg_rsrp       ◀ · · · · · │       │ SELECT ...                          │
│  实线曲线 = 表级血缘                 │                │ avg_sinr       ◀ · · · · · │       │                                      │
│  淡色虚线 = 字段级血缘               │                │ cell_id        ◀ · · · · · │       │ [同步到表定义] [复制]               │
│                                      │                └────────────────────────────┘       │                                      │
└──────────────────────────────────────┴──────────────────────────────────────────────────────┴──────────────────────────────────────┘
```

#### 图层语义

| 图层 | 节点/边 | 展示规则 | 交互 |
|------|---------|----------|------|
| 表节点 | X6 node + `Table` data | 默认展示目标表、直接上游表、直接下游表；按层级和方向扩展；展开后同列节点按实际高度重新避让 | 点击选中；拖动节点调整当前位置；节点内 `+/-` 展开或折叠字段 |
| 表级边 | X6 edge + 字段边实时聚合 | 实线曲线；前向/后向由左侧 checkbox 控制显示 | hover 显示字段边数量、涉及字段、计算类型分布 |
| 字段行 | node 内字段分行 + X6 port | 仅在表节点展开后显示；字段在一个节点内分行排列 | 字段行左右两侧提供 `in:<field>` / `out:<field>` 端口 |
| 字段级边 | X6 edge + `DERIVES_FROM` data | 淡色虚线曲线；仅当源表或目标表展开后显示 | hover 显示血缘关系；click 打开右侧编辑面板；端点可重连到其它字段 port |

#### 交互清单

| 交互 | 操作 | 效果 |
|------|------|------|
| 定位中心表 | URL param `?table=` 或左侧搜索 | 目标表高亮并自动居中 |
| 控制方向 | 勾选/取消 `前向`、`后向` checkbox | 隐藏或显示目标表的下游/上游表节点和表级边 |
| 展开字段 | 点击表节点 `+` 小按钮 | 表节点变高，在节点内分行显示所有字段和字段锚点；同列上游/下游节点按展开后的节点高度重排，避免字段列表覆盖相邻表 |
| 字段级血缘显示 | 展开相关表节点 | 在字段锚点之间显示淡色虚线曲线 |
| 边 hover | 鼠标移动到表级边或字段级边 | tooltip 展示源/目标、计算类型、表达式和参数摘要 |
| 边 click | 点击字段级边 | 右侧显示计算类型、参数和表达式编辑器 |
| 锚点拖动 | 拖动字段级边的源/目标锚点到其他字段 | 即时调用后端保存新端点；成功后刷新图和 SQL 预览，失败则回滚 |
| 图编辑联动 SQL | 新建/删除/改边、改计算类型、拖动端点 | 自动重新生成当前目标表 SQL 预览 |
| SQL 写回（第一版） | 在“导入 SQL”抽屉确认应用 | 将导入 SQL 写入 `Table.sql_logic` 并追加 `Change`；右侧“同步到表定义”按钮作为后续直接写回入口 |
| 导入 SQL | 点击“导入 SQL”并粘贴 `SELECT ... FROM ...` | 解析后展示字段/血缘变更预览；确认后第一版写入 `Table.sql_logic` 和 `Change`，字段/血缘变更应用为后续扩展 |
| 画布导航 | 拖拽、缩放、Mini-map | 支持大图定位和局部查看；全屏、全部折叠、展开当前表、刷新图按钮作为后续扩展 |

#### X6 画布数据模型

前端新增血缘画布适配层，把 `LineageGraphResponse` 转为 X6 的 nodes/edges。转换层是纯函数，便于单元测试和后续替换布局算法。

| 输入 | X6 输出 | 说明 |
|------|---------|------|
| `tables[]` | table nodes | node id 使用表名；node data 保存原始 `LineageTableNode` |
| `table_edges[]` | table edges | 表级边连接表节点主连接点或节点中心，不绑定具体字段 |
| `field_edges[]` | field edges | 字段级边连接 `source table out:<field>` 到 `target table in:<field>` |
| `expandedTables` | node height + ports | 折叠态固定高度；展开态按字段数计算高度并生成字段 port，同时参与同列节点纵向间距计算 |
| `includeUpstream/includeDownstream` | visible cells | 决定哪些节点、表级边、字段级边进入画布 |
| `selectedEdge` | selected X6 edge | 选中字段边高亮，并与右侧边编辑器同步 |

节点布局采用确定性三向布局：

- 中心目标表位于画布中间列。
- 上游表位于左侧，按距离目标表的层级向左扩展，同层多表纵向分布。
- 下游表位于右侧，按距离目标表的层级向右扩展，同层多表纵向分布。
- 同层多表纵向分布时使用节点实际高度加固定间距，展开字段列表后不会覆盖下一个表节点。
- 深度大于 1 时继续向左右扩展列；第一版不引入复杂自动布局，后续可接入 Dagre/ELK 优化。

#### X6 事件流

| X6 事件 | 前端处理 | 后端/API |
|---------|----------|----------|
| `node:click` | 选中表节点，保留后续表详情扩展入口 | 无 |
| 展开按钮 click | 更新 React `expandedTables`，重新计算 X6 graph data | 无 |
| `edge:mouseenter` / `edge:mouseleave` | 展示/隐藏 tooltip | 无 |
| `edge:click` | 若为字段级边，调用 `onSelectFieldEdge(edge)` | 无 |
| 字段级边端点重连 | 解析 source/target port，构造新的源/目标字段 | `PATCH /api/lineage/edges/:edge_id/endpoints` |
| 边编辑保存成功 | 高亮更新后的边，刷新图和 SQL 预览 | `PUT /api/lineage/edges/:edge_id` + `POST /api/lineage/sql/preview` |
| 端点重连失败 | 回滚到上一次 graph data，提示错误 | 后端返回 409/422 时保留原血缘 |

SQL 逻辑不存放在 X6 cell data 中。右侧 `LineageSqlPanel` 仍通过 `/api/lineage/sql/preview` 读取生成结果；字段级边编辑、端点重连、新建/删除边成功后，统一刷新 `lineage-graph` 与 `lineage-sql-preview`。

#### 第一版边界

- `/metadata/lineage` 使用 X6 作为可编辑血缘工作台；`/pipeline` 继续使用 G6 作为只读全局 DAG。
- 第一版不使用 `@antv/x6-react-shape`，优先用 X6 标准 SVG/HTML markup、自定义 port 和 edge tool 降低集成复杂度。
- 第一版不做批量框选、复制粘贴、撤销重做；这些属于后续图编辑器增强。
- 第一版不改后端数据模型；复用 `/api/lineage/graph`、`PUT /api/lineage/edges/:edge_id`、`PATCH /api/lineage/edges/:edge_id/endpoints` 和 SQL 预览/导入接口。
- 移动端保证页面可打开和左右面板可滚动；血缘编辑工作台的主要交互目标是桌面视口。

### 6.5 血缘维护、SQL 联动与 /chat

#### 计算类型模型

字段级血缘边不再只保存自由文本表达式，而是保存 `calc_type + calc_params + transform_expr`。`transform_expr` 是可读 SQL 片段，`calc_params` 是表单化配置，后端负责最小校验。

| calc_type | 含义 | 最小参数 | SQL 生成规则 |
|-----------|------|----------|--------------|
| DIRECT | 直通映射 | source field | `source.field AS target_field` |
| EXPRESSION | 普通表达式 | expression | `<transform_expr> AS target_field` |
| AGGREGATE | 聚合 | function, source field, group_by | `AVG/SUM/COUNT(...) AS target_field` 并汇总 `GROUP BY` |
| JOIN | 关联条件 | join_type, left/right keys | 生成 `JOIN ... ON ...` 片段 |
| WINDOW | 窗口计算 | partition_by, order_by, frame | 生成 `OVER (...)` |
| CONDITION | 条件计算 | condition, then, else | 生成 `CASE WHEN ... THEN ... ELSE ... END` |
| CONSTANT | 常量或派生值 | value 或 expression | 生成常量表达式 |

#### 编辑与保存语义

| 操作 | 保存策略 | 失败处理 |
|------|----------|----------|
| 新建字段级边 | 即时保存到 `DERIVES_FROM`，默认 `calc_type=DIRECT` 或用户选择的类型 | 字段不存在返回 404；成环返回 409 并高亮路径 |
| 修改计算类型/参数 | 保存 `calc_type/calc_params/transform_expr`，成功后刷新图 | 参数缺失时前端阻止提交，后端再次校验 |
| 拖动源/目标锚点 | 调用端点更新 API，后端做字段存在、重复边、循环检测 | 前端回滚到原连线并提示原因 |
| 删除字段级边 | 删除 `DERIVES_FROM`，成功后刷新图和 SQL 预览 | 若边已不存在，前端刷新图并提示已被其他操作删除 |
| 同步 SQL 到表定义 | 写入 `Table.sql_logic/sql_source/sql_updated_at`，追加 `Change` | 若图版本已变更，提示刷新后重试 |

#### SQL 生成

第一版只为当前目标表生成直接上游 Spark/Hive `SELECT` SQL，不递归展开多跳链路，不自动生成 CTE。多跳 CTE 和 Agent 辅助 SQL 生成作为后续扩展。

生成流程：
1. 读取目标表字段、直接上游字段级边和 `calc_type/calc_params/transform_expr`。
2. 选择主源表；多上游表按 `JOIN` 边参数生成 join 片段。
3. 为每个目标字段生成 SELECT 表达式。
4. 聚合字段收集 `GROUP BY`。
5. 若 JOIN 参数不足、字段无表达式或血缘不完整，SQL 标记为“不完整”，但仍展示可编辑预览。

#### SQL 导入

导入 SQL 第一版只支持用户选择目标表后粘贴 `SELECT ... FROM ...`。不在第一版解析完整 `CREATE TABLE`、`ALTER TABLE`、`INSERT SELECT`。

解析结果先进入预览，不直接写库：
- 新增字段、更新字段表达式、保留字段。
- 新增、修改、删除字段级血缘边。
- 推断出的 `calc_type/calc_params`。
- 无法识别的表达式、缺失 JOIN key、源表/字段不存在等风险。

用户确认后，第一版 `sql/apply` 写入 `Table.sql_logic/sql_dialect/sql_source/sql_updated_at` 并追加 `Change`；字段变更、血缘边变更和基于 `expected_graph_version` 的并发冲突校验作为后续扩展。如果用户取消，Neo4j 不发生变更。

#### 错误处理

- 循环血缘：后端返回成环路径，前端高亮相关字段和边。
- SQL 解析失败：保留原 SQL 文本，展示失败位置或无法识别片段。
- SQL 预览不完整：允许继续编辑图；第一版写入 `Table.sql_logic` 需通过“导入 SQL”确认应用，右侧“同步到表定义”直接写回为后续扩展。
- 并发冲突：前端随应用请求携带预览时的图版本；后端版本冲突校验作为后续扩展，落地后提示刷新重试。
- 图编辑导致 SQL 改变：右侧 SQL 区展示“生成 SQL”和“表上已保存 SQL”的差异提示。

#### 跳转 /chat 联动的上下文注入

右键选择「用 NL 修改...」时：

1. 路由切换到 `/chat?context=lineage&table=dws_cell_hourly&field=drop_rate`
2. Agent State 注入 context_prompt (对用户不可见):

```python
context_prompt = """
当前用户来自血缘图页面，正在查看:
  表: dws_cell_hourly
  字段: drop_rate
  当前表达式: CAST(SUM(CASE WHEN drop_flag=1 THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*)
  计算类型: AGGREGATE
  上游: dwd_session_qos.drop_flag
  当前表 SQL: SELECT ...
"""
```

3. 用户输入 NL → Agent 走 schema_evolve 路径
4. 变更完成后自动刷新血缘图和 SQL 预览

### 6.6 对话面板 (/chat)

#### 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  [会话列表 ☰]  NL 对话 — 新建对话                    [⊕ 新对话]│
├────────────────────────────────┬─────────────────────────────┤
│ 左侧: 对话流 (flex: 1)          │ 右侧: 产出面板 (400px)        │
│                                │                             │
│ ┌────────────────────────────┐ │ ┌─ 意图 Badge: 正向ETL ──┐  │
│ │ 🧑 我想看每个小区每小时的    │ │ │                         │  │
│ │   信号质量，覆盖强度和信噪比 │ │ │ 代码: Spark SQL         │  │
│ └────────────────────────────┘ │ │ ┌─────────────────────┐ │  │
│                                │ │ │ SELECT              │ │  │
│ ┌────────────────────────────┐ │ │ │   cell_id,           │ │  │
│ │ 🤖 找到两条相关链路。        │ │ │ │   hour_bucket,      │ │  │
│ │   推荐直接用已聚合好的       │ │ │ │   AVG(rsrp) AS      │ │  │
│ │   dws_cell_hourly。         │ │ │ │   avg_rsrp,         │ │  │
│ │                            │ │ │ │   ...               │ │  │
│ │ ┌─ 血缘预览 ─────────────┐ │ │ │ └─────────────────────┘ │  │
│ │ │ ods → dwd → dws ★     │ │ │ │ Monaco 高亮, 可编辑     │  │
│ │ └────────────────────────┘ │ │ └─────────────────────────┘  │
│ │                            │ │                             │
│ │ [✓ 直接用 dws_cell_hourly] │ │ ┌─ DryRun 结果 ─────────┐  │
│ │ [▸ 从明细自己聚合]         │ │ │ ✅ 成功  耗时 12.3s     │  │
│ └────────────────────────────┘ │ │ ┌────────┬───────────┐ │  │
│                                │ │ │cell_id │avg_rsrp   │ │  │
│ ┌────────────────────────────┐ │ │ │C00042  │-98.3      │ │  │
│ │ 🧑 直接用, 加掉话率>5%过滤  │ │ │ └────────┴───────────┘ │  │
│ └────────────────────────────┘ │ │ 仅展示 1 行             │  │
│                                │ └─────────────────────────┘  │
│ ┌────────────────────────────┐ │                             │
│ │ 🤖 生成完毕。确认跑沙箱？    │ │                             │
│ │ [▶ 沙箱试跑] [✎ 编辑代码]  │ │                             │
│ └────────────────────────────┘ │                             │
│                                │                             │
├────────────────────────────────┴─────────────────────────────┤
│  [输入框: 输入自然语言指令...]                          [发送 →]│
└──────────────────────────────────────────────────────────────┘
```

#### 对话面板功能清单

| 功能 | 说明 |
|------|------|
| 意图 Badge | 顶部显示: 正向ETL / 反向合成 / 元数据演进 |
| SSE 流式输出 | 对话气泡逐字呈现 |
| 血缘预览 mini 图 | Agent 推荐候选表时，右侧展示精简血缘图 |
| 选项按钮 | Agent 给出多选方案时渲染为按钮 |
| 代码卡片 | Monaco Editor 只读模式，语法高亮，可切换编辑 |
| DryRun 预览表格 | 沙箱完成后的 1 行结果，Ant Table 组件 |
| 分档柱状图 | 反向合成完成后展示各档分布，@antv/g2 |
| 约束滑块 | 反向合成中调整值域，Ant Slider |
| Diff 对比面板 | 元数据演进中左右对比旧/新公式 |
| 影响分析警告 | 元数据演进中列出受影响的下游表 |
| 缺失补齐卡片 | gap_check 发现缺口时展示建议 |
| 上下文注入 | 从 /metadata /lineage /pipeline 跳转时自动注入 |
| 错误定位 | 编译/执行失败时高亮错误行 |

### 6.7 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tables` | 表列表 (支持 ?layer= ?storage= ?search= ?category_id= ?include_children=true ?tag_ids= ?tag_match=any/all) |
| GET | `/api/tables/:id` | 表详情 + 字段列表 |
| POST | `/api/tables` | 新建表 |
| PUT | `/api/tables/:id` | 编辑表 |
| PUT | `/api/tables/:id/classification` | 更新表主分类和标签集合，写入 `IN_CATEGORY` / `TAGGED_WITH` 并追加 `Change` |
| DELETE | `/api/tables/:id` | 删除表 (含下游校验) |
| GET | `/api/metadata/categories/tree` | 分类树，返回大分类/小分类、表数量、active/protected/sort_order |
| POST | `/api/metadata/categories` | 新增分类；第一版只允许新增小分类 |
| PUT | `/api/metadata/categories/:id` | 改名、排序、描述等基础属性 |
| PATCH | `/api/metadata/categories/:id/move` | 移动小分类到其他大分类下 |
| PATCH | `/api/metadata/categories/:id/status` | 启用/停用分类 |
| GET | `/api/metadata/tags` | 标签分组和标签清单 |
| POST | `/api/metadata/tag-groups` | 新增标签分组 |
| PUT | `/api/metadata/tag-groups/:id` | 更新标签分组名称、排序、状态 |
| POST | `/api/metadata/tags` | 新增标签 |
| PUT | `/api/metadata/tags/:id` | 更新标签名称、分组、排序 |
| PATCH | `/api/metadata/tags/:id/status` | 启用/停用标签 |
| GET | `/api/fields/:id` | 字段详情 + 上游引用 |
| POST | `/api/fields` | 新建字段 |
| PUT | `/api/fields/:id` | 编辑字段 (含表达式/上游引用) |
| DELETE | `/api/fields/:id` | 删除字段 (含断链校验) |
| GET | `/api/lineage` | 血缘图数据 (?table= ?direction=up/down ?depth=1-5) — Cypher: `MATCH path=(f:Field)-[:DERIVES_FROM*1..$d]->(u) RETURN path` |
| GET | `/api/lineage/graph` | 血缘工作台图数据 (?table= ?depth= ?include_upstream= ?include_downstream=)，返回表节点、表级边、字段清单和字段级边 |
| POST | `/api/lineage/edges` | 新建字段级血缘边，入参为源字段、目标字段、计算类型、计算参数、转换表达式 |
| PUT | `/api/lineage/edges/:edge_id` | 更新血缘边计算类型、计算参数和转换表达式 |
| PATCH | `/api/lineage/edges/:edge_id/endpoints` | 拖动连线锚点后更新源字段或目标字段 |
| DELETE | `/api/lineage/edges/:edge_id` | 删除血缘边 |
| POST | `/api/lineage/sql/preview` | 根据当前或传入的血缘配置生成目标表 Spark/Hive SELECT SQL 预览 |
| POST | `/api/lineage/sql/import/preview` | 解析用户粘贴的 `SELECT ... FROM ...`，返回字段和血缘变更预览 |
| POST | `/api/lineage/sql/apply` | 用户确认 SQL 解析预览后，第一版写入 `Table.sql_logic` 并追加 `Change`；字段/血缘应用和图版本冲突校验为后续扩展 |
| GET | `/api/metadata/impact` | 删除/变更前下游影响预检查 (?table= ?field=) |
| POST | `/api/chat/start` | 新建对话 |
| POST | `/api/chat/message` | 发送消息 → SSE stream |
| GET | `/api/chat/:id/result` | 获取 dry-run 结果 |
| GET | `/api/chat/:id/history` | 获取对话历史 |
| POST | `/api/schema/apply` | 确认元数据变更 |
| GET | `/api/schema/evolution/:table` | 表级变更历史 |
| GET | `/api/yaml/export` | 导出 YAML (?table= 可选) |
| GET | `/api/yaml/preview/:table` | YAML 预览 (只读, 返回原始 YAML 文本) |
| GET | `/api/search` | 语义搜索 (?q= ?type=table/field) — BM25 + Dense + RRF |
| GET | `/api/pipeline` | 全局 Pipeline DAG 数据 (?mode=forward/reverse ?table=) |
| GET | `/api/health` | 服务健康检查 (FastAPI + Docker 各组件连通性) |

> 分页: 当前元数据规模较小 (10 表 / ~70 字段)，列表接口暂不分页。当表数超过 50 时，`GET /api/tables` 和 `GET /api/fields` 需增加 `?page=&size=` 参数。

### 6.8 Pipeline 可视化页面 (/pipeline)

`/pipeline` 和 `/metadata/lineage` 都会展示表级血缘，但职责不同：

| 页面 | 定位 | 图引擎 | 图粒度 | 是否编辑血缘 | SQL 能力 |
|------|------|--------|--------|--------------|----------|
| `/metadata/lineage` 血缘工作台 | 元数据和血缘维护入口 | X6 | 表级主图 + 展开后的字段级血缘 | 是。支持改边、拖锚点、计算类型、字段血缘 | 是。基于当前表血缘生成 SQL、导入 SQL 并写回 `Table.sql_logic` |
| `/pipeline` Pipeline 可视化 | 链路分析、路径观察和反向合成入口 | G6 | 主要是表级 DAG | 否。只读消费血缘结果，不维护字段级边 | 不负责维护表 SQL；只展示链路约束、路径和反向合成相关信息 |

因此，`/metadata/lineage` 是血缘建模源头，回答“这个表由哪些字段算出来、字段血缘怎么连、当前表 SQL 应该是什么”；`/pipeline` 是基于已有血缘聚合出的链路视图，回答“整体加工链路怎么走、上下游路径有哪些、约束如何沿链路传递”。`/pipeline` 不做字段级血缘编辑、不做 SQL 导入写回，也不承担 X6 图编辑器交互。

> **表级血缘聚合规则**：Pipeline 页面展示的是表级 DAG（节点 = 表）。表级血缘 = 该表所有字段沿 `:DERIVES_FROM` 关系到达的上游字段所属表的去重集合；边权 = 跨这两张表的字段级血缘边数。后端 `/api/pipeline` 通过 Cypher 聚合查询构建（`MATCH (t1:Table)-[:HAS_FIELD]->(f1)-[:DERIVES_FROM]->(f2)<-[:HAS_FIELD]-(t2) RETURN t1, t2, count(*) AS edge_weight`），不在 Neo4j 冗余存储表级血缘。

#### 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  Pipeline 可视化                    [正向 ETL ●] [反向合成 ○]  │
│                          [搜索表: dws_cell_hourly___]        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  正向 ETL 模式:                                               │
│                                                              │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────┐        │
│  │ods_ue   │    │dwd_session   │    │dws_cell      │        │
│  │_signal  │───→│_qos          │───→│_hourly       │        │
│  │ L1·Kafka│    │ L2·Hive      │    │ L3·Hive      │        │
│  │ 6字段    │    │ 8字段         │    │ 7字段         │        │
│  └─────────┘    └──────┬───────┘    └──────┬───────┘        │
│                        │                   │                │
│  ┌─────────┐           │                   │                │
│  │ods_gnb  │           │           ┌───────┴───────┐        │
│  │_alarm   │──┐        │           │ads_cell       │        │
│  │ L1·Kafka│  │        │           │_profile       │        │
│  │ 5字段    │  │  ┌─────┴──────┐   │ L4·StarRocks  │        │
│  └─────────┘  │  │dwd_ho      │   │ 5字段          │        │
│               ├─→│_event      │   └───────┬───────┘        │
│               │  │ L2·Hive    │           │                │
│               │  │ 7字段       │           ▼                │
│               │  └─────┬──────┘   ┌───────────────┐        │
│               │        │          │eval_user      │        │
│  ┌────────────┴────────┴──────────┤_score         │        │
│  │ dws_area_traffic               │ L5·StarRocks  │        │
│  │ L3·Hive                        │ 5字段          │        │
│  │ 6字段                           └───────────────┘        │
│  └────────────────────────────────┘                        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ 左侧图例                      右侧信息面板 (悬浮/选中时)       │
│ ┌──────────┐     ┌──────────────────────────────────────┐   │
│ │ ● ODS 层 │     │ 选中: dws_cell_hourly                  │   │
│ │ ● DWD 层 │     │ 层: DWS · Hive · 7 字段               │   │
│ │ ● DWS 层 │     │ 描述: 小区小时粒度汇总                 │   │
│ │ ● ADS 层 │     │ 上游: dwd_session_qos, dwd_ho_event  │   │
│ │ ● EVAL层 │     │ 下游: ads_cell_profile                │   │
│ └──────────┘     │ [查看字段详情] [💬 NL 查询]            │   │
│                  └──────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

#### 正向模式

- G6 DAG (有向无环图)，节点 = 表，边 = 血缘引用
- 节点颜色按层区分 (ODS绿 → DWD蓝 → DWS橙 → ADS紫 → EVAL红)
- 节点大小 = 字段数量映射
- 边标签显示引用字段数 (如 "3 字段引用于")
- 搜索框搜索表名 → 该节点高亮 + 上下游路径突出
- 层级滑块 [1~5] 控制展开半径
- 悬浮节点: 弹出表信息卡片 (字段/存储/描述/行数)
- 点击节点: 右侧面板展示详情 + [💬 NL 查询] 按钮 → /chat 跳转

#### 反向合成模式

- 切换 toggle 后图方向反转 (从右到左)
- 节点从目标表 (如 eval_user_score) 开始
- 每层边标签显示约束推断结果 (值域/分布)
- 点击节点可展开约束详情气泡

```
   反向模式:  ← 约束推断 ←
  ┌─────────┐    ┌──────────────┐    ┌──────────────────┐
  │ods_ue   │←───│dwd_session   │←───│ads_cell_profile  │←───┐
  │_signal  │    │_qos          │    │ 覆盖[0,100]       │    │
  │ rsrp    │    │ avg_rsrp     │    │ 容量[0,100]       │    │
  │ [-140,  │    │ AVG(rsrp)    │    │ 稳定[0,100]       │    │
  │  -44]   │    │              │    │ 移动[0,100]       │    │
  └─────────┘    └──────────────┘    └──────────┬─────────┘    │
                                                │              │
                                                ▼              │
                                     ┌──────────────────┐      │
                                     │eval_user_score ★│←─────┘
                                     │ qoe_score        │
                                     │ =0.5×cov+0.3×cap │
                                     │  +0.2×stab       │
                                     └──────────────────┘
```

#### 与 /chat 联动

1. 悬浮节点 → [💬 NL 查询] → 路由 `/chat?context=pipeline&table=dws_cell_hourly&mode=forward`
2. Agent State 注入上下文: 当前表、上下游链路、已有字段
3. 用户输入如 "从这个表出发查掉话率高于 5% 的小区" → 走正向 ETL 流程
4. 反向模式下类似: `/chat?context=pipeline&table=eval_user_score&mode=reverse`

### 6.9 元数据演化历史页面 (/schema-evolution)

#### 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  元数据演化历史                                                │
│  [搜索: 表名/字段...]  [表: 全部 ▼]  [操作: 全部 ▼]          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  变更时间线                                                   │
│                                                              │
│  ┌─ 2026-05-13 14:22 ──────────────────────────────────┐    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ ✏ UPDATE  eval_user_score.qoe_score  v1 → v2 │    │    │
│  │  │                                               │    │    │
│  │  │ 旧: 0.5×coverage + 0.3×capacity + 0.2×stab    │    │    │
│  │  │ 新: 0.6×signal_quality + 0.4×mobility_score   │    │    │
│  │  │                                               │    │    │
│  │  │ 影响下游: eval_net_health ⚠                    │    │    │
│  │  │                  [查看 YAML diff]              │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ 2026-05-13 10:32 ──────────────────────────────────┐    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ ➕ ADD  dwd_session_qos.jitter  (v1)          │    │    │
│  │  │                                               │    │    │
│  │  │ 类型: DOUBLE                                   │    │    │
│  │  │ 表达式: STDDEV(latency) OVER (...)             │    │    │
│  │  │ 上游: dwd_session_qos.latency                 │    │    │
│  │  │                  [查看 YAML diff]              │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                      │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ ✚ ADD  ods_gnb_load  (新表, v1)               │    │    │
│  │  │                                               │    │    │
│  │  │ 层: ODS · 存储: Kafka · 5 字段                  │    │    │
│  │  │ 分区键: timestamp                              │    │    │
│  │  │                  [查看 YAML]  [查看血缘]        │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ 2026-05-13 09:00 (初始) ───────────────────────────┐    │
│  │  ➕ 批量初始化: 10 张表, ~70 字段                     │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 功能详单

| 功能 | 入口 | 说明 |
|------|------|------|
| 时间线浏览 | 页面主体 | Ant Timeline 组件，按时间倒序 |
| 按表过滤 | 顶部 [表: 全部 ▼] | Select dropdown，列出所有表 |
| 按操作过滤 | 顶部 [操作: 全部 ▼] | ADD / UPDATE / DELETE |
| 按关键词搜索 | 顶部搜索框 | 模糊匹配表名/字段名 |
| 变更卡片 | 时间线内 | 显示操作类型 icon + 表.字段 + 版本号 + 旧→新 diff |
| 字段级 diff | 卡片内 inline | 旧公式 → 新公式 左右对比 |
| YAML diff | [查看 YAML diff] 按钮 | 调 `git diff HEAD~1 -- metadata-yaml/...yaml` 展示 |
| 查看血缘 | [查看血缘] 按钮 | 跳转 `/metadata/lineage?table=xxx` |
| 跳转来源 | URL `?table=xxx` | 从 /metadata 跳转时预过滤 |

#### YAML diff 实现

```python
@router.get("/api/schema/evolution/yaml-diff")
async def get_yaml_diff(table_name: str, version: int):
    """用 git show 取历史版本 YAML"""
    import subprocess
    yaml_path = f"metadata-yaml/{get_layer(table_name)}/{table_name}.yaml"

    # 当前版本
    current = Path(yaml_path).read_text(encoding="utf-8")

    # 历史版本: git show COMMIT:path
    # 通过 version→commit 映射表查找对应 commit
    commit = get_commit_for_version(table_name, version)
    if commit:
        historical = subprocess.check_output(
            ["git", "show", f"{commit}:{yaml_path}"],
            text=True
        )
    else:
        historical = "(初始版本)"

    return {"current": current, "historical": historical, "yaml_path": yaml_path}
```

#### 版本↔commit 映射

元数据变更时在 commit message 中标注 `table:xxx version:N`，反向查找即可：

```python
# schema_apply 节点写入后 commit 时：
commit_msg = f"schema_evolve: UPDATE {table_name}.{field_name} v{old}→v{new}"
# git log --grep "table:dws_cell_hourly version:2" → commit hash
```

---

## 7. 项目结构

```
data-gov/
├── .env                          # DeepSeek + DB 配置
├── base-compose.yml              # 基础设施容器
├── app-compose.yml               # FastAPI + React
├── metadata-yaml/                # 人工可读的 YAML 元数据副本
│   ├── L1-ODS/
│   ├── L2-DWD/
│   ├── L3-DWS/
│   ├── L4-ADS/
│   └── L5-EVAL/
├── init-scripts/
│   ├── 01_hive_init.sql
│   ├── 02_kafka_init.sh
│   ├── 03_starrocks_init.sql
│   ├── 04_sample_data.py
│   ├── 05_neo4j_init.py
│   ├── 06_neo4j_seed.py
│   └── 07_export_yaml.py
├── scripts/
│   ├── benchmark_semantic_search.py   # 语义检索 benchmark
│   └── generate_benchmark_queries.py  # 测试集生成
├── templates/                    # Sandbox 骨架
│   ├── spark-sql/
│   ├── flink-sql/
│   └── flink-java/
├── backend/
│   ├── main.py                   # FastAPI entry
│   ├── config.py                 # .env 加载
│   ├── metadata/
│   │   ├── graph.py              # Neo4j 驱动连接 + Cypher 封装 (官方 neo4j 驱动 / neomodel OGM)
│   │   ├── service.py            # CRUD (Cypher 实现, HTTP 与 Agent tools 共享)
│   │   └── seed.py               # 10 张表初始化
│   ├── agent/
│   │   ├── graph.py              # LangGraph StateGraph
│   │   ├── tools.py              # Agent tools
│   │   ├── prompts.py            # System prompts
│   │   └── deepseek.py           # LLM 连接
│   ├── search/
│   │   ├── searcher.py           # HybridSearcher (BM25+Dense+RRF)
│   │   └── embedder.py           # bge-small-zh embedding + ChromaDB
│   ├── sandbox/
│   │   ├── controller.py         # 编排
│   │   ├── yarn_submit.py        # YARN REST + subprocess
│   │   └── templates.py          # 模板注入
│   └── api/
│       ├── metadata.py           # /api/tables, /api/fields, /api/lineage
│       ├── chat.py               # /api/chat/*   SSE streaming
│       └── schema_evolution.py   # /api/schema/*
└── frontend/
    ├── vite.config.ts
    └── src/
        ├── pages/
        │   ├── Metadata.tsx
        │   ├── Chat.tsx
        │   ├── Pipeline.tsx
        │   ├── SchemaEvolution.tsx
        │   └── Health.tsx
        ├── components/
        │   ├── LineageWorkspaceGraph.tsx # X6 血缘工作台画布 (表级节点、字段端口、可编辑边)
        │   ├── PipelineDAG.tsx    # G6 Pipeline DAG 封装 (表级, 被 /pipeline 使用)
        │   ├── graphShared/       # 层级配色、图数据公共类型、Pipeline G6 与血缘 X6 数据转换
        │   │   └── lineageX6Adapter.ts # LineageGraphResponse -> X6 nodes/edges 的纯函数转换
        │   ├── CodeCard.tsx       # Monaco 代码卡片
        │   ├── DryRunPreview.tsx  # 1 行预览表格
        │   ├── ConstraintSlider.tsx # 反向合成约束调整
        │   ├── DiffPanel.tsx      # 旧/新公式左右对比
        │   ├── EvolutionTimeline.tsx # 变更时间线
        │   ├── HealthPanel.tsx    # 健康检查面板
        │   └── ChatStream.tsx     # SSE 流式对话
        └── api/
            └── client.ts          # fetch 封装 (含 SSE ReadableStream)
```

---

## 8. 实施阶段 & E2E 验收用例

| Phase | 内容 |
|-------|------|
| **Phase 1** | Docker 栈搭建（含 Neo4j）+ Neo4j 元数据图初始化 + 元数据 CRUD API |
| **Phase 2** | LangGraph Agent 搭建 + 3 条对话路径 + 沙箱 |
| **Phase 3** | React 前端 + 血缘图 + 对话面板 + Pipeline 可视化 |

### 依赖关系

```
Phase 1 ⇒ Phase 2 ⇒ Phase 3
    (Docker  + 元数据必须先就绪，Agent 才能查 Schema；UI 需要 Agent 和 API 都好)
```

### Phase 1 验收用例

| # | 用例 | 步骤 | 预期结果 |
|---|------|------|----------|
| P1-1 | 一键启动基础设施 | 执行 `docker compose -f base-compose.yml up -d` | 所有 10 个服务 Running (Health: healthy)，HDFS NameNode UI :9870 可访问，YARN RM UI :8088 可访问 |
| P1-2 | Hive 外部表可读写 | 通过 Spark Shell 建外部表 → INSERT 10 行 → SELECT COUNT(*) | 返回 10 |
| P1-3 | Kafka Topic 可生产消费 | 往 `ods_ue_signal` topic 生产 5 条 JSON → consumer 从 earliest 消费 | 消费到 5 条，内容一致 |
| P1-4 | StarRocks 可查询 | `04_sample_data.py` 执行后，StarRocks FE 查询 `SELECT COUNT(*) FROM ads_cell_profile` | 返回 > 0 |
| P1-5 | Neo4j 元数据初始化 + YAML 导出 | 执行 `05_neo4j_init.py` → `06_neo4j_seed.py`，cypher-shell 查询 `MATCH (t:Table) RETURN count(t)`；执行 `07_export_yaml.py` | 返回 10；`metadata-yaml/` 下生成 10 个 .yaml 文件，按层分目录，gate-lint 通过 |
| P1-5b | Neo4j 约束已建立 | cypher-shell 执行 `SHOW CONSTRAINTS` 与 `SHOW INDEXES` | 返回 ≥ 4 条约束 (Table.id/Table.name/Field.id/Change.id 唯一) 与 ≥ 3 条索引 (Field.name / Change.changed_at / Change.table_name) |
| P1-6 | 元数据 CRUD API | POST 建一张新表 → GET /api/tables → GET /api/fields → PUT 修改字段表达式 → GET 校验 | 每步返回 200，数据一致 |
| P1-7 | 血缘查询 API | GET `/api/lineage?table=dwd_session_qos&direction=down` 查下游血缘 | 返回 `dws_cell_hourly`, `dws_area_traffic` 中至少 2 条字段级血缘边 |
| P1-8 | 反向合成数据入对应存储 | 调用 `generate_fake_data(table="dwd_session_qos", rows=5)` → Spark SQL 查询 Hive 表 `dwd_session_qos` | 返回 5 行，字段值域合法 (rsrp ∈ [-140,-44], sinr ∈ [-20,30]) |

### Phase 2 验收用例

| # | 用例 | 步骤 | 预期结果 |
|---|------|------|----------|
| P2-1 | 正向 ETL: NL→Spark SQL | 发送消息 "用 `ods_ue_signal` 按 cell_id 计算每小区小时的平均 RSRP 和 SINR，写入 Hive 表 `dws_cell_hourly`" | 返回 Spark SQL，schema_lookup 工具被调用过，代码语法正确 |
| P2-2 | 正向 ETL: NL→Flink SQL | 发送消息 "从 Kafka `ods_gnb_alarm` 读告警，按 gnb_id 做 5 分钟滚动窗口 COUNT" | 返回 Flink SQL，含 CREATE TABLE (Kafka source) + TUMBLE 窗口 + sink 定义 |
| P2-3 | 正向 ETL: NL→Java Flink | 发送消息 "写一个 Flink DataStream 程序，从 Kafka 读 UE 信号，过滤 RSRP<-110 的弱覆盖，写入 HDFS" | 返回完整 Java main class，含 Kafka source / filter / StreamingFileSink |
| P2-4 | Spark SQL 沙箱执行 | 对 P2-1 生成的 SQL 调 dry_run | 返回 `DryRunResult(success=True, preview_row={...})`，preview_row 含 cell_id/h avg_rsrp/avg_sinr |
| P2-5 | Flink SQL 沙箱执行 | 对 P2-2 生成的 Flink SQL 调 dry_run | HDFS sink 写入成功，回读 1 行，字段匹配 |
| P2-6 | Java Flink 沙箱执行 | 对 P2-3 生成的 Java 代码调 dry_run | 编译成功 → JAR 上传 → YARN 提交 → FINISHED → HDFS 回读 1 行，弱覆盖 IMSI 列表合法 |
| P2-7 | 沙箱编译失败自动重试 | 注入一个有语法错误的 Flink SQL (故意拼错 `SLECT`)，观察沙箱层 `execute_with_retry` 行为 | 沙箱层第 1 轮编译失败 → 解析 maven 错误 → LLM 修正 → 第 2 轮通过；返回 `DryRunResult(success=True)`，Agent 层 `iteration_count = 1`（沙箱层重试不计入 Agent 层） |
| P2-8 | 元数据演进: NL→新增字段 | 发送消息 "给 `dwd_session_qos` 加一个 `jitter` 字段，用相邻采样的 latency 标准差计算" | schema_diff 预览显示 1 条新增字段，用户确认后 Neo4j 新建 Field 节点 + HAS_FIELD 边 + Change 节点，对应 YAML 文件更新，GET /api/fields 可查到，`dwd_session_qos.yaml` 含 `jitter` 字段 |
| P2-9 | 元数据演进: 一致性校验 | 发送消息 "删除 `ods_ue_signal` 的 `rsrp` 字段" | schema_validate 检测到 `dwd_session_qos.avg_rsrp` 和 `dwd_ho_event` 依赖此字段，返回警告不执行，要求先处理下游 |
| P2-10 | 反向合成数据生成 | 发送消息 "给定 `eval_user_score` 的评估逻辑，生成 10 行测试数据，覆盖优秀/良好/差三档" | 反推约束 (qoe_score 0-100) → 生成 3 档数据 → 写入 HDFS → 读回校验: 确实有 >80 / 50-80 / <50 的行 |
| P2-11 | 缺失对象检测 (gap_check) | 发送消息 "我要每个小区每小时的平均基站负载和信号质量" — 信号质量已有，基站负载无 | gap_check 返回 1 条 missing_table gap，Web 端展示补齐建议卡片，含建议表名/字段/层级 |
| P2-12 | 缺失对象自动补齐 | 在 P2-11 的补齐建议卡片点击 [确认并继续] | schema_evolve 子流程自动执行: 新建 ods_gnb_load (ODS, Kafka, 5 字段) → Neo4j 写入 Table+Field+HAS_FIELD+Change 节点 + YAML 生成 → schema_lookup 重新查询 → 继续 code_generate 产出含基站负载的 SQL |
| P2-13 | 缺失字段检测 | 人为删除 dwd_session_qos.avg_sinr 字段后，发送 "从会话 QoS 查信噪比分布" | gap_check 检测到 keyword=信噪比 field=avg_sinr 缺失，建议在 dwd_session_qos 补回该字段 |

### Phase 3 验收用例

| # | 用例 | 步骤 | 预期结果 |
|---|------|------|----------|
| P3-1 | 元数据浏览页面: 分层+搜索 | 打开 `/metadata` → 看到 10 张表按层分组 → 切换 L1 过滤 → 仅显示 2 张 ODS 表 → 搜索框输入 "会话" | 列表过滤为 dwd_session_qos，右侧字段列表含 avg_rsrp/avg_sinr 等 |
| P3-2 | 元数据浏览: 字段详情+上游 tooltip | 点击 `dws_cell_hourly` → hover `avg_rsrp` 字段 | tooltip 浮层显示上游: dwd_session_qos.avg_rsrp，表达式: AVG(rsrp) |
| P3-3 | 元数据维护: 新建表 | 点击 [+ 新建表] → 填写表名/层/存储 → 添加 5 个字段 → 保存 | Neo4j 写入 Table 节点 + 5 个 Field 节点 + 5 条 HAS_FIELD 边成功，GET /api/tables 新增 1 条，metadata-yaml/ 下生成对应 .yaml |
| P3-4 | 元数据维护: 编辑字段表达式 | 点击 `dws_cell_hourly.drop_rate` → 抽屉打开 → Monaco 编辑表达式 → 保存 | Field 节点 expression 属性更新，version +1，previous_expr (JSON 字符串) 追加旧版本 |
| P3-5 | 元数据维护: 删除字段被拒绝 | 点击删除 `ods_ue_signal.rsrp` | 系统检测到 dwd_session_qos.avg_rsrp 依赖此字段，弹出下游影响警告，拒绝删除 |
| P3-6 | 血缘工作台: X6 表级默认图 | 在表详情页点击「查看血缘」→ URL 跳转 `/metadata/lineage?table=dws_cell_hourly` | X6 画布默认只渲染表级血缘，表节点用实线曲线连接，目标表高亮并自动居中 |
| P3-7 | 血缘方向控制 | 取消勾选左侧「前向」或「后向」checkbox | 对应方向的表节点和表级边被隐藏；重新勾选后恢复 |
| P3-8 | 字段展开与字段级血缘 | 点击 `dws_cell_hourly` 表节点展开按钮 | X6 节点内分行显示字段并生成字段 port；展开相关表后出现淡色虚线字段级边，hover 显示源字段、目标字段、计算类型和表达式 |
| P3-9 | 血缘边结构化编辑 | 点击字段级边 → 修改计算类型为 `AGGREGATE` 并填写参数 → 保存 | `DERIVES_FROM` 更新 `calc_type/calc_params/transform_expr`，图刷新，右侧 SQL 预览同步变化 |
| P3-10 | 拖动锚点改血缘端点 | 在 X6 画布中拖动字段级边源锚点到另一个上游字段 port | 后端即时保存新端点并做循环校验；成功后图与 SQL 预览刷新，失败时连线回滚 |
| P3-10a | 基于血缘生成 SQL | 选中目标表 → 点击「生成 SQL」或完成一次血缘编辑 | 右侧展示当前目标表直接上游 Spark/Hive SELECT SQL；第一版“同步到表定义”按钮展示占位提示，直接写回为后续扩展 |
| P3-10b | SQL 导入预览应用 | 选择目标表 → 粘贴 `SELECT ... FROM ...` → 点击解析 | UI 展示字段变更、血缘变更、计算类型推断和风险；确认后第一版写入 `Table.sql_logic` 和 Change，字段/血缘应用为后续扩展 |
| P3-10c | 血缘图→/chat 联动 | 右键 `dws_cell_hourly.drop_rate` → [用 NL 修改] | 路由跳转 `/chat?context=lineage&table=dws_cell_hourly&field=drop_rate`，Agent State 注入当前表达式、计算类型、上游信息和当前表 SQL |
| P3-11 | 对话面板: 流式输出 + Badge | 打开 `/chat` → 新建对话 → 输入 "计算每小区小时平均覆盖强度" | SSE 逐字流式输出，classifier badge 显示「正向ETL」，右侧展示血缘 mini 图推荐方案 |
| P3-12 | 对话面板: 代码卡片 + DryRun 预览 | 对话完成 → 代码卡片显示 Spark SQL (Monaco 高亮) → 点击 [▶ 沙箱试跑] | 右侧代码面板可编辑，DryRun 结果卡片显示 ✅ 成功 + 1 行 Ant Table |
| P3-13 | 对话面板: 缺失补齐子流程 UI | 输入 "按基站负载和信号质量做评估" → gap_check 发现缺失 | 对话气泡下方显示补齐建议卡片，[确认并继续] [我自己定义] [跳过] 三个按钮 |
| P3-14 | 对话面板: 反向合成约束滑块 | 输入 "给用户评分流程造测试数据" → 约束反推面板展示 | 三档约束表格每行有 Slider 可拖拽调整值域，行数可输入 |
| P3-15 | 对话面板: 反向合成结果图表 | 点击 [生成数据] → 等待沙箱完成 | 结果区显示写入概览 (各层行数) + 预览 Ant Table + 分档 G2 柱状图 |
| P3-16 | 对话面板: 元数据演进 Diff | 输入 "把 qoe_score 公式权重改成 0.6/0.4" → diff 预览 | 左右对比面板: 旧公式 vs 新公式，下方 ⚠ eval_net_health 影响警告 |
| P3-17 | 元数据演进: UI 变更确认 | 点击 [确认更新] | Neo4j (Field 更新 + Change 节点新增) + YAML 写入，跳转 `/schema-evolution` 可看到变更时间线，字段版本 v1→v2 |
| P3-18 | Pipeline 可视化: 正向 ETL | 打开 `/pipeline` → 正向模式 → 搜索链路 | G6 渲染完整 DAG: ods_ue_signal → dwd_session_qos → dws_cell_hourly → ads_cell_profile → eval_user_score |
| P3-19 | Pipeline 可视化: 反向合成 | 切换反向模式 → 选 eval_user_score pipeline | 逆向图: eval → 约束推断 → 逐层回溯 → 数据生成器入口 |
| P3-20 | Pipeline→/chat 联动 | 在 Pipeline 图上选中 `dws_cell_hourly` 节点 → 点击 [💬 NL 查询] | 跳转 /chat，自动注入上下文，用户输入 "加一个切换成功率过滤" → 走正向 ETL 流程 |
| P3-21 | 全链路: 搜索→血缘→对话→预览 | `/metadata` 搜索 "信噪比" → 进入血缘图 → 右键 [NL 过滤低 SINR] → /chat 生成 SQL → 沙箱跑通 → 预览 1 行 | 60s 内完成，页面跳转流程通顺 |
| P3-22 | 元数据演化历史 | `/schema-evolution` 查看变更时间线 → 按 dwd_session_qos 过滤 → 点击 v1→v2 | 左右 diff 面板显示字段新增详情 |

---

## 9. 非功能要求

- **安全**: `.env` 不提交，`.gitignore` 排除；API 无鉴权 (本地验证栈)
- **可调试**: Neo4j Browser http://localhost:7474 直接查看图与运行 Cypher；HDFS 数据本地可读
- **清理**: Sandbox 临时目录自动清理；Docker `docker-compose down -v` 全清
- **文档**: 代码即文档，10 张表元数据自带描述和表达式
