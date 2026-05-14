"""生成 60 条 benchmark queries -> benchmark/benchmark_queries.yaml。

类型 A (30): 从 SEED_TABLES 派生 - table.description 同义词替换 + 字段描述衍生
类型 B (20): 人工编写的 LLM 风格 (不同角色提问)
类型 C (10): 对抗样本 (模糊/歧义/跨域)
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from backend.seed.tables import SEED_TABLES

# ---- Type A 模板 ----
SYNONYM_PROBES: list[tuple[str, str, str, str]] = [
    # (target_table, query, expected_field_or_empty, difficulty)
    ("ods_ue_signal", "查 UE 终端的 RSRP/SINR 采样", "rsrp", "easy"),
    ("ods_ue_signal", "用户终端的信噪比原始数据", "sinr", "easy"),
    ("ods_ue_signal", "终端上报的信号原始流", "", "easy"),
    ("ods_gnb_alarm", "基站告警的原始数据", "", "easy"),
    ("ods_gnb_alarm", "gnodeB 故障告警流", "alarm_type", "medium"),
    ("ods_gnb_alarm", "基站故障严重度", "severity", "easy"),
    ("dwd_session_qos", "用户会话级别的 QoS 明细", "", "easy"),
    ("dwd_session_qos", "会话粒度的平均覆盖强度", "avg_rsrp", "medium"),
    ("dwd_session_qos", "会话粒度的平均信噪比", "avg_sinr", "medium"),
    ("dwd_session_qos", "会话延时和抖动", "latency", "medium"),
    ("dwd_ho_event", "终端切换事件记录", "", "easy"),
    ("dwd_ho_event", "用户基站间切换是否成功", "ho_result", "medium"),
    ("dwd_ho_event", "切换的源小区和目标小区", "source_cell", "easy"),
    ("dws_cell_hourly", "小区小时粒度的平均覆盖强度", "avg_rsrp", "easy"),
    ("dws_cell_hourly", "小区每小时的掉话率", "drop_rate", "easy"),
    ("dws_cell_hourly", "每个小区每小时的平均吞吐量", "avg_throughput", "easy"),
    ("dws_cell_hourly", "小区小时粒度切换成功率", "ho_success_rate", "easy"),
    ("dws_cell_hourly", "小区每小时会话总数", "total_sessions", "medium"),
    ("dws_area_traffic", "区域级别每小时的流量统计", "", "easy"),
    ("dws_area_traffic", "区域级活跃用户数", "active_users", "medium"),
    ("dws_area_traffic", "区域每小时的峰值吞吐量", "peak_throughput", "medium"),
    ("ads_cell_profile", "小区画像的覆盖能力指标", "coverage_score", "medium"),
    ("ads_cell_profile", "小区容量评分", "capacity_score", "medium"),
    ("ads_cell_profile", "小区稳定性评分", "stability_score", "medium"),
    ("ads_cell_profile", "小区综合 KPI 评分", "composite_kpi", "medium"),
    ("eval_user_score", "用户画像 QoE 评分", "qoe_score", "medium"),
    ("eval_user_score", "用户日期信息", "date", "easy"),
    ("eval_user_score", "用户综合体验评估打分", "qoe_score", "medium"),
    ("eval_net_health", "网络整体健康度指标", "health_index", "medium"),
    ("eval_net_health", "网络健康度指标", "health_index", "medium"),
]
assert len(SYNONYM_PROBES) == 30, "Type A 需要恰好 30 条"

# ---- Type B (人工 LLM 风格, 20 条) ----
TYPE_B: list[dict] = [
    {"query": "帮我看看最近一段时间信号质量差的用户都有哪些", "expected_table": "dwd_session_qos", "expected_fields": ["avg_sinr", "avg_rsrp"], "difficulty": "medium"},
    {"query": "我想知道哪些基站老是告警", "expected_table": "ods_gnb_alarm", "expected_fields": ["gnb_id", "alarm_type"], "difficulty": "medium"},
    {"query": "运维老板要看每个小区的整体打分", "expected_table": "ads_cell_profile", "expected_fields": ["coverage_score"], "difficulty": "medium"},
    {"query": "查一下用户在 5G 切换时成功的比例", "expected_table": "dws_cell_hourly", "expected_fields": ["ho_success_rate"], "difficulty": "hard"},
    {"query": "我要看高峰时段哪些区域流量爆了", "expected_table": "dws_area_traffic", "expected_fields": ["total_throughput", "peak_throughput"], "difficulty": "hard"},
    {"query": "评估一下网络是否健康", "expected_table": "eval_net_health", "expected_fields": ["health_index"], "difficulty": "medium"},
    {"query": "我想分析用户 QoE 体验分数的分布", "expected_table": "eval_user_score", "expected_fields": ["qoe_score"], "difficulty": "easy"},
    {"query": "拉一下小区每小时的平均掉话率", "expected_table": "dws_cell_hourly", "expected_fields": ["drop_rate"], "difficulty": "easy"},
    {"query": "查覆盖弱的用户的明细", "expected_table": "dwd_session_qos", "expected_fields": ["avg_rsrp"], "difficulty": "medium"},
    {"query": "把所有终端在基站间的切换都列出来", "expected_table": "dwd_ho_event", "expected_fields": [], "difficulty": "easy"},
    {"query": "看一下哪些用户有最新日期记录", "expected_table": "eval_user_score", "expected_fields": ["date"], "difficulty": "easy"},
    {"query": "想看小区在某段时间内的吞吐能力", "expected_table": "dws_cell_hourly", "expected_fields": ["avg_throughput"], "difficulty": "medium"},
    {"query": "找网络稳定性差的小区", "expected_table": "ads_cell_profile", "expected_fields": ["stability_score"], "difficulty": "medium"},
    {"query": "做用户体验报告需要打分原始数据", "expected_table": "eval_user_score", "expected_fields": ["qoe_score"], "difficulty": "medium"},
    {"query": "ARPU 高但是体验差的用户有哪些", "expected_table": "eval_user_score", "expected_fields": ["qoe_score"], "difficulty": "hard"},
    {"query": "查每个区域每小时的活跃用户数", "expected_table": "dws_area_traffic", "expected_fields": ["active_users"], "difficulty": "easy"},
    {"query": "我要监测掉线率突增的小区", "expected_table": "dws_cell_hourly", "expected_fields": ["drop_rate"], "difficulty": "medium"},
    {"query": "想知道告警持续了多久", "expected_table": "ods_gnb_alarm", "expected_fields": ["duration"], "difficulty": "medium"},
    {"query": "看用户从一个塔切到另一个塔的情况", "expected_table": "dwd_ho_event", "expected_fields": ["source_cell", "target_cell"], "difficulty": "hard"},
    {"query": "做容量评估的输入数据", "expected_table": "ads_cell_profile", "expected_fields": ["capacity_score"], "difficulty": "hard"},
]
assert len(TYPE_B) == 20

# ---- Type C (对抗, 10 条) ----
TYPE_C: list[dict] = [
    {"query": "网络状况怎么样", "expected_table": "eval_net_health", "expected_fields": ["health_index"], "difficulty": "hard"},
    {"query": "找出网络里有问题的地方", "expected_table": "eval_net_health", "expected_fields": ["health_index"], "difficulty": "hard"},
    {"query": "啥都不知道, 给我看个总体情况", "expected_table": "eval_net_health", "expected_fields": [], "difficulty": "hard"},
    {"query": "把所有的数据都给我", "expected_table": "ods_ue_signal", "expected_fields": [], "difficulty": "hard"},
    {"query": "做一份分析报告", "expected_table": "eval_user_score", "expected_fields": [], "difficulty": "hard"},
    {"query": "我说的那个表", "expected_table": "dwd_session_qos", "expected_fields": [], "difficulty": "hard"},
    {"query": "RSRP 是什么意思", "expected_table": "ods_ue_signal", "expected_fields": ["rsrp"], "difficulty": "medium"},
    {"query": "查 5G 数据", "expected_table": "ods_ue_signal", "expected_fields": [], "difficulty": "hard"},
    {"query": "qoe 评分公式是啥", "expected_table": "eval_user_score", "expected_fields": ["qoe_score"], "difficulty": "medium"},
    {"query": "切换成功率怎么算", "expected_table": "dws_cell_hourly", "expected_fields": ["ho_success_rate"], "difficulty": "medium"},
]
assert len(TYPE_C) == 10


def main(output_path: str = "benchmark/benchmark_queries.yaml") -> None:
    queries = []
    qid = 1

    # Type A
    for table, query, fld, diff in SYNONYM_PROBES:
        item = {
            "id": f"Q{qid:03d}",
            "type": "A",
            "query": query,
            "expected_table": table,
            "expected_fields": [fld] if fld else [],
            "difficulty": diff,
        }
        queries.append(item)
        qid += 1

    # Type B
    for q in TYPE_B:
        queries.append({
            "id": f"Q{qid:03d}",
            "type": "B",
            **q,
        })
        qid += 1

    # Type C
    for q in TYPE_C:
        queries.append({
            "id": f"Q{qid:03d}",
            "type": "C",
            **q,
        })
        qid += 1

    assert len(queries) == 60
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(queries, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    # 校验 expected_table 全部存在于 SEED_TABLES
    valid_tables = {t["name"] for t in SEED_TABLES}
    for q in queries:
        assert q["expected_table"] in valid_tables, f"Bad table: {q['expected_table']}"

    print(f"Wrote {len(queries)} queries to {out}")


if __name__ == "__main__":
    main()
