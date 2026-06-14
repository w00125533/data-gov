# 17. 详细功能矩阵

本文把 2026-05-13 文档中的完整功能树逐项映射到目标态。它的作用是防止后续实施时只保留治理 API，而遗漏 UI、Agent、反向合成、沙箱、联动和维护类交互。

状态定义：

- `Implemented`: 当前已有实现或已有核心能力。
- `Transition`: 有旧实现，但目标态需要迁移。
- `Planned`: 目标态明确，尚未实现。
- `Future`: 目标态保留，排在后续阶段。

## 1. 基础设施管理

| 编号 | 功能 | 目标态 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| 1.1 | Docker 栈一键启动/停止 | 使用 `../shared-data-infra` 启动共享基础设施，本工程 `app-compose.yml` 启动应用服务。 | Transition | compose config + health。 |
| 1.2 | 初始化脚本执行 | shared infra 执行基础组件初始化，应用侧执行 GaussDB migration、样例 metadata 注册和 Chroma 初始化。 | Planned | init log + API 查询。 |
| 1.3 | 配置管理 | `.env` 或 compose env 管理 Spring Boot、Python Agent、frontend、SDK 示例配置。 | Implemented | compose config 渲染。 |
| 1.4 | 基础设施健康面板 | UI `/health` 展示 shared infra 和应用服务状态。 | Planned | UI-HEALTH-001。 |
| 1.5 | 本地清理 | 应用容器和应用卷可清理，shared infra 数据卷不被本工程误删。 | Planned | 手工和脚本检查。 |

## 2. 元数据管理 `/metadata`

| 编号 | 功能 | 目标态 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| 2.1.1 | 分层过滤 | ODS、DWD、DWS、ADS、EVAL。 | Planned | UI-META-001。 |
| 2.1.2 | 搜索 | assetCode、assetName、fieldName、description、业务术语。 | Planned | UI 搜索命中 RNO 样例。 |
| 2.1.3 | 表详情 | 字段、表达式、上游、binding、owner、domain、queryable。 | Planned | 详情字段完整。 |
| 2.2.1 | 新建表 | 通过 Spring Boot API 创建 metadata、fields、binding、lineage。 | Future | UI 表单 + API 验收。 |
| 2.2.2 | 编辑表 | 编辑名称、描述、owner、queryable、binding。 | Future | PATCH API + UI 回显。 |
| 2.2.3 | 删除表 | 运行时取消注册，展示下游依赖警告。 | Future | DELETE API + notification。 |
| 2.2.4 | 新建字段 | 添加字段并可选择上游字段。 | Future | PATCH metadata。 |
| 2.2.5 | 编辑字段 | Monaco 编辑表达式，展示字段血缘和影响。 | Future | ADV-001。 |
| 2.2.6 | 删除字段 | 下游依赖阻断或确认迁移。 | Future | ADV-002。 |
| 2.3.1 | 导出 YAML | 从 GaussDB 生成 YAML，不作为主存储。 | Planned | YAML 文件和 UI 预览。 |
| 2.3.2 | YAML 预览 | 详情页抽屉只读展示。 | Planned | UI-META-001。 |
| 2.3.3 | YAML diff | 基于 git diff 或历史导出对比。 | Future | ADV-003。 |
| 2.4 | 跳转演化历史 | `/schema-evolution?metadataId=...`。 | Planned | UI-SCHEMA-001。 |

## 3. 血缘图 `/metadata/lineage`

| 编号 | 功能 | 目标态 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| 3.1.1 | 字段级 DAG | X6 节点字段端口 + fieldEdges。 | Planned | UI-LIN-002。 |
| 3.1.2 | 展开/折叠层级 | 按 depth 和节点展开状态控制。 | Planned | X6 画布验收。 |
| 3.1.3 | 正向/反向切换 | direction up/down/full。 | Implemented partly | UI-LIN-001。 |
| 3.1.4 | 节点拖拽 + 缩放 | X6 支持拖拽、缩放、适配视图。 | Planned | X6 缩放拖拽测试。 |
| 3.1.5 | 边详情 | 展示 expression、transformType、source/target 字段。 | Implemented partly | 正式血缘 UI 验收。 |
| 3.1.6 | Mini-map | X6 minimap 插件。 | Planned | X6 mini map 验收。 |
| 3.1.7 | 全屏模式 | 画布全屏，工具栏固定。 | Future | 视觉验收。 |
| 3.2.1 | 编辑节点 | 右键 metadata 节点打开编辑抽屉。 | Future | API + UI。 |
| 3.2.2 | 新建血缘边 | 端口拖拽建字段级边。 | Future | ADV-004。 |
| 3.2.3 | 编辑边表达式 | Monaco 编辑 expression。 | Future | PATCH lineage。 |
| 3.2.4 | 删除边/节点 | 删除血缘边或取消注册 metadata。 | Future | 影响确认。 |
| 3.2.5 | 从血缘图新建下游表 | 以当前节点作为 upstream 预填表单。 | Future | 表单预填验收。 |
| 3.3.1 | 跳转 Chat | 带入 metadataId、field、edge 上下文。 | Planned | UI-CHAT-002。 |
| 3.3.2 | NL 修改后刷新 | Chat 提交变更后 lineage reload。 | Future | Agent 全链路。 |
| 3.3.3 | 新建对象实时更新 | API 成功后更新 X6 图。 | Future | UI 交互验收。 |

## 4. NL 对话 `/chat`

| 编号 | 功能 | 目标态 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| 4.1.1 | 新建对话 | 创建 session 并清空上下文。 | Planned | UI-CHAT-001。 |
| 4.1.2 | 对话历史 | 展示历史 session、intent、更新时间。 | Planned | UI 检查。 |
| 4.1.3 | SSE 输出 | 流式渲染 token 或结构化事件。 | Existing API | Chat E2E。 |
| 4.1.4 | 意图 badge | forward_etl、reverse_synth、schema_evolve。 | Planned | UI-CHAT-001。 |
| 4.1.5 | 上下文注入 | metadata、lineage、pipeline 跳转自动带 context。 | Planned | UI-CHAT-002。 |
| 4.2.1 | 业务语义匹配 | 语义搜索表和字段。 | Existing backend | Agent test + UI。 |
| 4.2.2 | 候选表推荐 | 展示命中原因、血缘预览、方案对比。 | Planned | Chat card 验收。 |
| 4.2.3 | 代码生成 | Spark SQL、Flink SQL、Java Flink。 | Existing backend | Agent tests。 |
| 4.2.4 | 代码卡片 | Monaco 高亮、复制、编辑、dry-run。 | Planned | UI-CHAT-001。 |
| 4.2.5 | 沙箱试跑 | YARN 提交，结果回读。 | Existing backend | SBOX tests。 |
| 4.2.6 | 预览结果 | 表格展示 1 到 20 行。 | Planned | dry-run UI。 |
| 4.2.7 | 缺失对象补齐 | gap_check -> schema_evolve。 | Existing backend partly | Agent E2E。 |
| 4.2.8 | 失败自动重试 | Agent 层和沙箱层重试分离。 | Existing backend partly | retry tests。 |
| 4.3.1 | 评估 pipeline 匹配 | 根据目标评估表定位上游链路。 | Planned | reverse_synth test。 |
| 4.3.2 | 全链路上游溯源 | pipeline_parse + lineage。 | Existing backend partly | pipeline tests。 |
| 4.3.3 | 约束反推面板 | 变量、值域、来源。 | Future | UI 反向合成验收。 |
| 4.3.4 | 分档滑块 | 优秀、良好、较差三档值域和行数。 | Future | 视觉验收。 |
| 4.3.5 | 缺失对象补齐 | 反向合成也能触发 gap proposal。 | Future | Agent E2E。 |
| 4.3.6 | 数据生成代码 | Java Flink 逐层生成。 | Existing backend partly | sandbox E2E。 |
| 4.3.7 | 沙箱执行 + 分层写入 | 写 Kafka/Hive/StarRocks。 | Future | infra E2E。 |
| 4.3.8 | 结果预览 | 表格 + 分档柱状图。 | Future | UI 图表验收。 |
| 4.3.9 | 写入对应存储 | 按 sourceType 写入。 | Future | Docker E2E。 |
| 4.4.1 | 目标字段匹配 | schema_lookup + context。 | Existing backend | Agent tests。 |
| 4.4.2 | 一致性校验 | 重名、断链、循环依赖。 | Existing backend partly | schema_validate tests。 |
| 4.4.3 | Diff 面板 | 旧值 vs 新值。 | Planned | UI-SCHEMA-001。 |
| 4.4.4 | 下游影响 | lineage impact warning。 | Future | deletion blocking。 |
| 4.4.5 | 确认后写入 | Spring Boot API 写 GaussDB。 | Planned | Agent + API E2E。 |
| 4.4.6 | 变更历史 | metadata_event + schema evolution。 | Planned | UI-SCHEMA-001。 |
| 4.5.1 | BM25 | jieba + 术语保护。 | Existing backend | search tests。 |
| 4.5.2 | Dense | bge + ChromaDB。 | Existing backend | search integration。 |
| 4.5.3 | RRF + rerank | 混合检索和 LLM 兜底。 | Existing backend | benchmark。 |
| 4.5.4 | 增量同步 | metadata 变更后 upsert Chroma。 | Planned | sync tests。 |

## 5. Pipeline `/pipeline`

| 编号 | 功能 | 目标态 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| 5.1.1 | 完整链路展示 | X6 展示 ODS 到 EVAL。 | Planned | UI-PIPE-001。 |
| 5.1.2 | 上下游突出 | 选中节点高亮邻接路径。 | Planned | UI-PIPE-001。 |
| 5.1.3 | 节点悬浮卡 | 字段、存储、表达式、owner。 | Future | 视觉验收。 |
| 5.1.4 | NL 查询跳转 | Pipeline 节点到 Chat context。 | Planned | UI-CHAT-002。 |
| 5.2.1 | 逆向图 | 目标表 -> 约束 -> 生成器。 | Planned | UI-PIPE-002。 |
| 5.2.2 | 约束气泡 | 每层显示值域和来源。 | Future | 视觉验收。 |
| 5.2.3 | 图上调整约束 | 在 X6 节点或侧栏修改。 | Future | reverse UI。 |
| 5.3.1 | Chat 联动 | 选中节点进入对话。 | Planned | UI-CHAT-002。 |
| 5.3.2 | Lineage 联动 | 共享 metadataId 和 edge context。 | Planned | UI-LIN-001。 |
| 5.3.3 | 正反切换 | Segmented 控制 mode。 | Planned | UI-PIPE-001。 |

## 6. Schema Evolution `/schema-evolution`

| 编号 | 功能 | 目标态 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| 6.1 | 时间线 | 按时间倒序展示 metadata_event。 | Planned | UI-SCHEMA-001。 |
| 6.2 | 过滤 | 表、字段、操作类型、关键词。 | Planned | UI-SCHEMA-001。 |
| 6.3 | 详情 diff | oldValue -> newValue。 | Planned | UI-SCHEMA-001。 |
| 6.4 | YAML diff | git show 或导出历史。 | Future | ADV-003。 |
| 6.5 | 预过滤跳转 | 从 metadata 带参数进入。 | Planned | UI-META-001。 |

## 7. Sandbox

| 编号 | 功能 | 目标态 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| 7.1 | Maven 编译 | 模板工程编译。 | Existing backend | SBOX tests。 |
| 7.2 | Spark/Flink 提交 | 提交到 shared infra YARN。 | Existing backend | infra sandbox。 |
| 7.3 | HDFS 回读 | 读取预览结果。 | Existing backend | sandbox infra。 |
| 7.4 | 自动重试 | 编译和执行失败重试。 | Existing backend | retry tests。 |
| 7.5 | 临时目录清理 | TTL 清理。 | Planned | cleanup tests。 |

## 8. Health

| 编号 | 功能 | 目标态 | 状态 | 验收 |
| --- | --- | --- | --- | --- |
| 8.1 | 状态卡片 | governance、Agent、GaussDB、Kafka、StarRocks、Hive、Spark、Chroma。 | Planned | UI-HEALTH-001。 |
| 8.2 | 自动刷新 | 30 秒刷新。 | Future | UI timer test。 |
| 8.3 | 异常高亮 | DOWN/DEGRADED 高亮和错误摘要。 | Planned | mock error test。 |
