# 14. UI 与 X6 交互详细规格

本文恢复 2026-05-13 文档中的 UI 信息量，并按目标态修订：所有交互式图画布统一使用 AntV X6，包括字段级血缘图、表级血缘图、正向 Pipeline DAG 和反向合成链路图。当前 G6 实现只作为迁移来源。

## 1. UI 总体原则

- 第一屏必须是可操作的治理工作台，不做营销式首页。
- SaaS/治理后台风格应安静、密集、适合扫描和重复操作。
- 页面之间必须可联动：metadata、lineage、pipeline、chat、schema evolution 不能成为孤岛。
- 所有目标能力都要可在 UI 上看到入口，即使实现分期延后，也要在路线中有明确位置。
- X6 图画布承担复杂关系表达和维护操作，表格和抽屉承担结构化详情编辑。

## 2. 页面地图

| 页面 | 路由 | 核心目标 |
| --- | --- | --- |
| 元数据管理 | `/metadata` | 浏览、筛选、详情、字段、YAML、跳转血缘和演化历史。 |
| 血缘图 | `/metadata/lineage` | 字段级血缘、表级血缘、上下游、边详情、维护。 |
| NL 对话 | `/chat` | 正向 ETL、反向合成、元数据演进、dry-run 和结果预览。 |
| Pipeline | `/pipeline` | 正向 ETL DAG、反向合成链路、节点联动。 |
| Schema Evolution | `/schema-evolution` | 变更时间线、diff、YAML diff、影响分析。 |
| Sandbox Preview | `/sandbox/preview` 或 Chat 内嵌 | 编译、提交、YARN 状态、预览和错误。 |
| Health | `/health` | 应用服务和 shared infra 状态。 |

## 3. `/metadata` 详细设计

### 3.1 布局

```text
┌────────────────────────────────────────────────────────────────────┐
│ 顶部过滤区：关键词、层级、类型、来源、负责人、状态、刷新            │
├───────────────┬────────────────────────────────────────────────────┤
│ 左侧列表       │ 右侧详情                                           │
│ - 表卡片       │ - 基础信息                                          │
│ - 层级标签     │ - 字段表格                                          │
│ - sourceType   │ - binding                                          │
│ - queryable    │ - lineage summary                                  │
│               │ - YAML preview / evolution / chat / lineage actions │
└───────────────┴────────────────────────────────────────────────────┘
```

### 3.2 过滤项

| 控件 | 类型 | 行为 |
| --- | --- | --- |
| 关键词 | Input.Search | 按 assetCode、assetName、description、fieldName 搜索。 |
| 层级 | Segmented | ODS、DWD、DWS、ADS、EVAL、全部。 |
| metadataType | Select | TABLE、VIEW、TOPIC。 |
| sourceType | Select | HIVE、STARROCKS、GAUSSDB、ICEBERG、KAFKA。 |
| owner | Select 或 Input | 按负责人过滤。 |
| status | Select | ACTIVE、REMOVED_BY_SNAPSHOT、UNREGISTERED。 |

### 3.3 列表卡片

每个数据集卡片展示：

- assetCode。
- assetName。
- layer。
- sourceType。
- owner。
- queryable。
- 字段数。
- 最近更新时间。
- 状态标签。

卡片点击后加载详情。列表必须支持空状态、加载状态和错误状态。

### 3.4 详情区

详情区包含：

- 基础信息：名称、编码、类型、领域、负责人、描述、状态。
- 物理绑定：sourceType、catalog、database、table、qualifiedName、properties。
- 字段表：fieldName、fieldType、nullable、description、expression、ordinal、upstream count。
- 操作：查看血缘、打开 Chat、查看演化历史、YAML 预览、编辑元数据。

字段行操作：

- 查看字段血缘。
- 编辑表达式。
- 删除字段前影响分析。
- 从字段跳转 Chat。

### 3.5 YAML 抽屉

YAML 抽屉只读显示当前导出版本：

- 文件路径。
- YAML 内容。
- 最近生成时间。
- 复制按钮。
- 查看 diff 按钮。

### 3.6 跳转规则

| 来源操作 | 目标 |
| --- | --- |
| 查看血缘 | `/metadata/lineage?source=formal&metadataId=...&direction=up` |
| 查看字段血缘 | `/metadata/lineage?source=formal&metadataId=...&field=...` |
| 用 NL 修改 | `/chat?context=metadata&metadataId=...&field=...` |
| 演化历史 | `/schema-evolution?metadataId=...` |

## 4. `/metadata/lineage` X6 详细设计

### 4.1 画布模型

X6 节点类型：

| 节点 | 用途 |
| --- | --- |
| `metadata-node` | 表、视图、topic。 |
| `field-port-row` | 节点内部字段行或端口。 |
| `job-node` | 可选，用于显示作业、SQL 或转换节点。 |
| `group-node` | 可选，用于层级分组或服务域分组。 |

边类型：

| 边 | 用途 |
| --- | --- |
| `table-lineage-edge` | 表级或资产级关系。 |
| `field-lineage-edge` | 字段端口到字段端口。 |
| `job-transform-edge` | 作业节点连接输入输出。 |

### 4.2 节点视觉

metadata 节点包含：

- Header: assetCode、layer、sourceType、status。
- Body: 字段行列表。
- Footer: 字段数量、上游数量、下游数量。

字段行包含：

- fieldName。
- fieldType。
- nullable 标记。
- expression 标记。
- 左侧 input port。
- 右侧 output port。

端口规则：

- 上游字段 output port 连接下游字段 input port。
- 表级边可以连接节点 header 端口。
- 端口 hover 展示字段描述和表达式。

### 4.3 工具栏

| 控件 | 类型 | 功能 |
| --- | --- | --- |
| 资产搜索 | AutoComplete | 搜索 metadata 并加载血缘。 |
| 方向 | Segmented | 上游、下游、全链路。 |
| 深度 | Slider / Select | 1 到 10。 |
| 粒度 | Segmented | 表级、字段级、混合。 |
| 布局 | Select | LR、TB、分层、手动。 |
| 缩放 | Icon buttons | 放大、缩小、适配视图。 |
| MiniMap | Toggle | 显示或隐藏 mini map。 |
| 全屏 | Icon button | 进入画布全屏。 |

### 4.4 交互

| 操作 | 结果 |
| --- | --- |
| 点击节点 | 右侧面板展示 metadata 详情。 |
| 点击字段 | 右侧面板展示字段详情和上下游字段。 |
| 点击边 | 右侧面板展示表达式、转换类型、来源作业。 |
| 双击节点 | 展开或折叠字段行。 |
| 拖动画布 | 平移。 |
| 滚轮 | 缩放。 |
| 框选 | 多选节点或边。 |
| 拖拽端口到端口 | 创建字段级血缘草案。 |
| 右键节点 | 打开节点上下文菜单。 |
| 右键边 | 打开边上下文菜单。 |

### 4.5 右键菜单

节点菜单：

- 查看详情。
- 编辑元数据。
- 新增字段。
- 查看上游。
- 查看下游。
- 用 NL 修改。
- 从此新建下游表。
- 查看演化历史。

字段菜单：

- 编辑字段。
- 编辑表达式。
- 查看字段血缘。
- 删除字段影响分析。
- 用 NL 修改字段。

边菜单：

- 查看表达式。
- 编辑表达式。
- 删除血缘边。
- 生成 Chat 上下文。
- 查看影响范围。

### 4.6 拖拽建边流程

```text
用户从 source field output port 拖到 target field input port
  -> UI 创建 draft edge
  -> 打开表达式抽屉
  -> 用户填写 transformType 和 expression
  -> UI 调用 Spring Boot PATCH metadata 或 lineage API
  -> 服务端校验字段存在和循环依赖
  -> 成功后刷新 lineage
```

抽屉字段：

- source metadata。
- source field。
- target metadata。
- target field。
- lineageType 固定为 FIELD。
- transformType。
- expression。
- operator。
- reason。

### 4.7 空态和错误态

空态：

- 未选择资产：提示搜索或从 metadata 页面跳转。
- 无血缘：显示当前资产卡片和“创建血缘”入口。
- 字段级血缘为空但表级存在：展示表级边并提示可补充字段级映射。

错误态：

- metadataId 不存在。
- lineage API 失败。
- 图数据字段缺失。
- X6 渲染失败。

错误态必须保留重试按钮和请求上下文。

## 5. `/pipeline` X6 详细设计

### 5.1 正向 ETL DAG

节点类型：

- source topic。
- staging table。
- transform job。
- aggregate table。
- serving table。
- evaluation output。

正向模式默认从 ODS 到 EVAL 左到右：

```text
ods_ue_signal -> dwd_session_qos -> dws_cell_hourly -> ads_cell_profile -> eval_user_score
ods_gnb_alarm -> eval_net_health
dwd_ho_event -> ads_neighbor_pair
```

节点展示：

- assetCode。
- layer。
- storage。
- field count。
- job count。
- queryable。

边展示：

- lineageType。
- transformType。
- expression summary。
- field mapping count。

### 5.2 反向合成链路

反向模式从目标评估表回溯：

```text
eval_user_score
  -> required score buckets
  -> ads_cell_profile constraints
  -> dws_cell_hourly constraints
  -> dwd_session_qos constraints
  -> generated ODS/Kafka samples
```

X6 节点包括：

- target evaluation table。
- score bucket node。
- constraint node。
- generator node。
- output write node。

约束节点展示：

- 变量。
- 值域。
- 行数。
- 约束来源。
- 可编辑状态。

### 5.3 Pipeline 与 Chat 联动

| 操作 | Chat context |
| --- | --- |
| 节点“NL 查询” | metadataId、assetCode、selected upstream/downstream。 |
| 边“解释转换” | source、target、expression、lineageType。 |
| 反向节点“生成数据” | target asset、bucket constraints、row count。 |
| 缺失节点“补齐” | gap proposal seed。 |

## 6. `/chat` 详细设计

### 6.1 布局

```text
┌──────────────┬──────────────────────────────┬──────────────────────┐
│ 会话列表      │ 对话流                         │ 结果/上下文面板        │
│ - 新建        │ - user message                 │ - matched assets       │
│ - 历史        │ - assistant stream             │ - code card            │
│ - intent tag  │ - gap card                     │ - dry-run result       │
│              │ - confirmation card            │ - lineage preview      │
└──────────────┴──────────────────────────────┴──────────────────────┘
```

### 6.2 对话气泡

Assistant 气泡可以包含：

- 自然语言解释。
- 意图 badge。
- 候选表列表。
- 血缘预览。
- 代码卡片。
- diff 卡片。
- gap 建议卡片。
- dry-run 状态。

### 6.3 代码卡片

代码卡片使用 Monaco：

- 语言：Spark SQL、Flink SQL、Java。
- 支持复制。
- 支持编辑。
- 支持格式化。
- 支持 dry-run。
- dry-run 后展示结果面板。

### 6.4 gap 建议卡片

字段：

- gap 类型。
- 推荐表名或字段名。
- 所属层级。
- 字段列表。
- 来源说明。
- 风险说明。

操作：

- 确认并继续。
- 我自己定义。
- 跳过。

### 6.5 元数据演进 diff

Diff 面板展示：

- 旧字段定义。
- 新字段定义。
- 旧表达式。
- 新表达式。
- 新增或删除的 lineage edges。
- 下游影响。
- 订阅影响。

确认后调用 Spring Boot API，不允许 Python 直接写库。

## 7. `/schema-evolution` 详细设计

过滤区：

- 表。
- 字段。
- 操作类型。
- 时间范围。
- 关键词。

时间线卡片：

- 操作类型图标。
- assetCode。
- fieldName。
- version 或 event id。
- 操作人。
- 变更时间。
- oldValue/newValue diff。
- 影响对象数量。

YAML diff：

- 当前 YAML。
- 历史 YAML。
- Git commit。
- 对应 metadata_event。

## 8. `/health` 详细设计

健康状态分组：

| 分组 | 项 |
| --- | --- |
| 应用服务 | frontend、governance-server、Python Agent。 |
| 主存储 | GaussDB。 |
| 检索 | Chroma、embedding model。 |
| 消息 | Kafka、notification topic。 |
| 查询 | StarRocks、catalog、sample query。 |
| Lakehouse | Hive Metastore、HiveServer2、HDFS、YARN、Spark。 |
| 配置 | shared infra network、app-compose profile。 |

每个状态卡片：

- 状态：UP、DOWN、DEGRADED、UNKNOWN。
- 最近检查时间。
- latency。
- 错误摘要。
- 操作建议。

## 9. 可视化验收要求

每个页面必须至少有：

- 首屏非空检查。
- 无框架错误 overlay。
- console error/warn 检查。
- 一个主要交互。
- 截图证据。
- 真实数据或 mock 数据说明。

X6 画布额外检查：

- canvas 非空。
- 至少一个节点可见。
- 至少一条边可见。
- 点击节点后详情更新。
- 点击边后详情更新。
- 缩放或适配视图不报错。
- mobile viewport 不出现不可恢复遮挡。
