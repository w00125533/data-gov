# 07. UI 目标设计

## 1. 技术口径

目标态 UI 技术栈：

- React + TypeScript + Vite。
- Ant Design。
- AntV X6，统一用于血缘图和 Pipeline DAG。
- Monaco，用于 SQL、Flink、Java、表达式和 diff 查看编辑。
- Playwright，用于可视化和端到端验收。

当前前端实现使用 G6 渲染血缘图和 Pipeline DAG。G6 是过渡实现，不是目标态图画布。目标态统一迁移到 X6，以支持字段端口、复杂边路由、拖拽建边、右键菜单、画布状态和维护操作。

## 2. `/metadata`

目标能力：

- 分层过滤：ODS、DWD、DWS、ADS、EVAL。
- 按表名、字段名、描述和业务术语搜索。
- 表详情展示字段、表达式、分区、存储、负责人、领域和查询开关。
- 字段详情展示上游字段、表达式、版本和影响对象。
- YAML 预览和 YAML diff 入口。
- 跳转 `/metadata/lineage`。
- 跳转 `/schema-evolution`。
- 创建和编辑元数据的入口。

## 3. `/metadata/lineage`

目标能力：

- X6 字段级血缘画布。
- 节点表示数据集，字段以端口或字段行表示。
- 字段级边连接源字段端口和目标字段端口。
- 支持上游、下游和全链路视图。
- 支持层级深度、缩放、拖拽、框选、mini map、全屏。
- 点击边展示表达式、作业、转换类型和创建来源。
- 右键节点可编辑元数据、添加字段、跳转 Chat。
- 右键字段可修改表达式、查看影响、发起 NL 修改。
- 拖拽建边后填写转换表达式并通过 Spring Boot API 写入。

## 4. `/chat`

目标能力：

- 新建对话和历史对话。
- SSE 流式输出。
- 意图 badge：正向 ETL、反向合成、元数据演进。
- 上下文注入：从 metadata、lineage、pipeline 跳转时自动带入表、字段和血缘信息。
- 代码卡片：Spark SQL、Flink SQL、Java Flink。
- Dry-run 按钮和结果预览。
- gap 补齐建议卡片。
- 元数据演进 diff 和确认更新。
- 失败重试过程展示。

## 5. `/pipeline`

目标能力：

- X6 正向 ETL Pipeline DAG。
- X6 反向合成链路图。
- 节点表示表、作业、约束推断、生成器和结果。
- 支持正向/反向切换。
- 支持上下游高亮、节点详情、hover 信息和 mini map。
- 节点可跳转 Chat 或血缘图。
- 反向合成模式展示约束值域和行数配置。

## 6. `/schema-evolution`

目标能力：

- 变更时间线。
- 按表、字段、操作类型和关键词过滤。
- 展示旧值和新值 diff。
- 展示 YAML diff。
- 展示下游影响警告。
- 跳转对应元数据和血缘图。

## 7. Sandbox / Preview

目标可以实现为独立页面，也可以作为 Chat 右侧结果面板：

- Maven 编译结果。
- Spark/Flink 提交结果。
- YARN application id 和终态。
- HDFS 或目标存储预览数据。
- 错误解析和重试历史。
- 生成数据分档图表。

## 8. `/health`

目标能力：

- Spring Boot governance-server 状态。
- Python Agent 状态。
- GaussDB、Kafka、StarRocks、Hive、Spark/YARN、Chroma 状态。
- 自动刷新。
- 异常高亮和最近检查时间。

## 9. 分期说明

所有页面目标态完整保留。实施时可以按阶段交付：

1. 先将现有页面接入 Spring Boot `/rest/...` 和 GaussDB 模型。
2. 再迁移血缘图和 Pipeline DAG 到 X6。
3. 再补高级维护交互、Agent 全链路和治理后台增强。
