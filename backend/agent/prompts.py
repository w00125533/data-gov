"""所有 LLM prompt 模板。{placeholder} 使用 str.format 风格。"""
from __future__ import annotations


CLASSIFIER_PROMPT = """你是无线网络数据治理助手的意图分类器。基于最近的对话历史判断用户当前消息属于哪一类意图。

候选意图：
- forward_etl: 正向 ETL - 用户希望查询/聚合/转换现有表数据
- reverse_synth: 反向合成 - 用户希望根据评估目标生成测试数据
- schema_evolve: 元数据演进 - 用户希望新增/修改/删除表或字段

最近对话历史:
{history}

上一轮意图: {prev_intent}
当前上下文来源: {context_source}

返回严格的 JSON (不要 Markdown 包裹):
{{"intent": "forward_etl|reverse_synth|schema_evolve", "confidence": 0.0-1.0, "reason": "..."}}
"""


EXTRACT_PROMPT = """从用户消息抽取业务实体。意图: {intent}

用户消息: {msg}

对于 forward_etl 返回:
{{"target_entities": ["..."], "source_hints": ["..."], "code_type_hint": "spark_sql|flink_sql|java_flink|auto"}}

对于 reverse_synth 返回:
{{"eval_target": "...", "row_count_hint": 10, "buckets_hint": [{{"label":"优","range":[80,100]}}]}}

严格 JSON, 不要 Markdown。
"""


SCHEMA_EVOLVE_PROMPT = """用户要求修改元数据 schema。请把自然语言转为 schema diff JSON。

用户请求: {user_request}

当前相关表 schema:
{current_schema}

返回严格 JSON 数组, 每条变更形如:
{{"operation": "ADD_FIELD|DELETE_FIELD|UPDATE_FIELD|ADD_TABLE|DELETE_TABLE",
  "table": "...",
  "field": "...",
  "data_type": "DOUBLE|INT|STRING|...",
  "expression": "...",
  "upstream": [{{"table": "...", "field": "..."}}],
  "layer": "ODS|DWD|DWS|ADS|EVAL",
  "storage_type": "KAFKA|HIVE|STARROCKS",
  "fields": [...]}}
"""


PROPOSE_PROMPT = """根据检测到的元数据缺口和用户原始需求，提出补齐建议。

缺口列表: {gaps}
用户请求: {user_request}

对每个 missing_table 缺口给出新建表草案; 对每个 missing_field 缺口给出新建字段草案。
返回严格 JSON 数组, 每条同 SCHEMA_EVOLVE_PROMPT 的 schema diff 格式。
确保层级 (ODS/DWD/...) 与存储 (KAFKA/HIVE/STARROCKS) 推断合理。
"""


CODE_GEN_PROMPT = """你是无线网络数据 ETL 代码生成器。

意图: {intent}
代码类型: {code_type}
相关 schema:
{schema}

用户请求: {user_request}

上一轮失败反馈 (若有, 修复后再生成):
{error_feedback}

输出要求:
1. 一段可直接提交沙箱执行的代码
2. 用 fenced code block 包裹 (```spark-sql / ```flink-sql / ```java)
3. 代码外的解释保持简短
"""


PRESENTER_REPHRASE_PROMPT = """把以下技术结果改写为面向用户的对话回复, 自然但不啰嗦。

意图: {intent}
结果摘要 JSON:
{summary_json}

直接输出回复正文, 不要前缀寒暄。
"""
