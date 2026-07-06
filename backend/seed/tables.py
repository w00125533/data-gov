"""Single source of truth for the 10 seed tables, ~65 fields, and ~45 lineage edges.

Used by:
- init-scripts/06_neo4j_seed.py — writes nodes + relationships to Neo4j
- init-scripts/07_export_yaml.py — materializes metadata-yaml/L*-*/ *.yaml
- tests/api/test_seed_data.py — invariants
- tests/api/test_lineage.py — P1-7 expectations

Field schema:
    {"name", "type", "nullable", "partition", "expression" (optional), "description"}
"""
from __future__ import annotations

LAYER_PRIORITY = {"ODS": 1, "DWD": 2, "DWS": 3, "ADS": 4, "EVAL": 5}


DEFAULT_CATEGORY_TREE: list[dict] = [
    {
        "code": "environment",
        "name": "环境",
        "children": [
            {"code": "environment.geo", "name": "地理"},
            {"code": "environment.scenario", "name": "场景"},
            {"code": "environment.weather", "name": "天气"},
            {"code": "environment.machine-room", "name": "机房"},
        ],
    },
    {
        "code": "equipment",
        "name": "设备",
        "children": [
            {"code": "equipment.fronthaul", "name": "前传"},
            {"code": "equipment.clock", "name": "时钟"},
            {"code": "equipment.backhaul", "name": "回传"},
            {"code": "equipment.antenna-feeder", "name": "天馈"},
            {"code": "equipment.power", "name": "电源"},
            {"code": "equipment.rf", "name": "射频"},
            {"code": "equipment.bbu", "name": "BBU"},
        ],
    },
    {
        "code": "network",
        "name": "网络",
        "children": [
            {"code": "network.coverage", "name": "覆盖"},
            {"code": "network.interference", "name": "干扰"},
            {"code": "network.traffic", "name": "话务"},
            {"code": "network.capacity", "name": "容量"},
            {"code": "network.rate", "name": "速率"},
            {"code": "network.latency", "name": "时延"},
            {"code": "network.quality", "name": "质量"},
            {"code": "network.access", "name": "接入"},
            {"code": "network.retain", "name": "保持"},
            {"code": "network.mobility", "name": "移动"},
            {"code": "network.packet-loss", "name": "丢包"},
            {"code": "network.energy", "name": "能耗"},
        ],
    },
    {
        "code": "user",
        "name": "用户",
        "children": [
            {"code": "user.identity", "name": "标识信息"},
            {"code": "user.terminal", "name": "终端信息"},
            {"code": "user.plan", "name": "套餐信息"},
            {"code": "user.location", "name": "位置信息"},
            {"code": "user.service", "name": "业务信息"},
            {"code": "user.activity", "name": "活动信息"},
        ],
    },
    {
        "code": "business",
        "name": "业务",
        "children": [
            {"code": "business.live", "name": "直播"},
            {"code": "business.video", "name": "视频"},
            {"code": "business.game", "name": "游戏"},
            {"code": "business.web", "name": "网页"},
            {"code": "business.scan", "name": "扫码"},
            {"code": "business.upload-download", "name": "上传下载"},
            {"code": "business.im", "name": "即时通信"},
            {"code": "business.production", "name": "生产"},
            {"code": "business.mobile-ai", "name": "Mobile AI"},
        ],
    },
    {
        "code": "source-data",
        "name": "源数据",
        "children": [
            {"code": "source-data.counter", "name": "话统"},
            {"code": "source-data.chr", "name": "CHR"},
            {"code": "source-data.config", "name": "配置"},
            {"code": "source-data.engineering", "name": "工参"},
            {"code": "source-data.map", "name": "电子地图"},
        ],
    },
]


DEFAULT_TAG_GROUPS: list[dict] = [
    {
        "code": "table-layer",
        "name": "表层级",
        "tags": [
            {"code": "layer.ods", "name": "ODS"},
            {"code": "layer.dwd", "name": "DWD"},
            {"code": "layer.dws", "name": "DWS"},
            {"code": "layer.ads", "name": "ADS"},
            {"code": "layer.eval", "name": "EVAL"},
        ],
    },
    {
        "code": "source",
        "name": "来源类型",
        "tags": [
            {"code": "source.counter", "name": "话统"},
            {"code": "source.chr", "name": "CHR"},
            {"code": "source.config", "name": "配置"},
            {"code": "source.engineering", "name": "工参"},
            {"code": "source.map", "name": "电子地图"},
        ],
    },
    {
        "code": "network-domain",
        "name": "网络域",
        "tags": [
            {"code": "network.coverage", "name": "覆盖"},
            {"code": "network.interference", "name": "干扰"},
            {"code": "network.traffic", "name": "话务"},
            {"code": "network.capacity", "name": "容量"},
            {"code": "network.rate", "name": "速率"},
            {"code": "network.latency", "name": "时延"},
            {"code": "network.quality", "name": "质量"},
            {"code": "network.access", "name": "接入"},
            {"code": "network.retain", "name": "保持"},
            {"code": "network.mobility", "name": "移动"},
            {"code": "network.packet-loss", "name": "丢包"},
            {"code": "network.energy", "name": "能耗"},
        ],
    },
    {
        "code": "equipment-domain",
        "name": "设备域",
        "tags": [
            {"code": "equipment.fronthaul", "name": "前传"},
            {"code": "equipment.clock", "name": "时钟"},
            {"code": "equipment.backhaul", "name": "回传"},
            {"code": "equipment.antenna-feeder", "name": "天馈"},
            {"code": "equipment.power", "name": "电源"},
            {"code": "equipment.rf", "name": "射频"},
            {"code": "equipment.bbu", "name": "BBU"},
            {"code": "equipment.machine-room", "name": "机房"},
        ],
    },
    {
        "code": "user-domain",
        "name": "用户域",
        "tags": [
            {"code": "user.identity", "name": "标识信息"},
            {"code": "user.terminal", "name": "终端信息"},
            {"code": "user.plan", "name": "套餐信息"},
            {"code": "user.location", "name": "位置信息"},
            {"code": "user.service", "name": "业务信息"},
            {"code": "user.activity", "name": "活动信息"},
        ],
    },
    {
        "code": "business-domain",
        "name": "业务域",
        "tags": [
            {"code": "business.live", "name": "直播"},
            {"code": "business.video", "name": "视频"},
            {"code": "business.game", "name": "游戏"},
            {"code": "business.web", "name": "网页"},
            {"code": "business.scan", "name": "扫码"},
            {"code": "business.upload-download", "name": "上传下载"},
            {"code": "business.im", "name": "即时通信"},
            {"code": "business.production", "name": "生产"},
            {"code": "business.mobile-ai", "name": "Mobile AI"},
        ],
    },
]


TABLE_CLASSIFICATION: dict[str, dict] = {
    "ods_ue_signal": {
        "category_path": ["源数据", "CHR"],
        "category_code": "source-data.chr",
        "tags": ["ODS", "覆盖", "质量", "射频", "标识信息"],
        "tag_codes": ["layer.ods", "network.coverage", "network.quality", "equipment.rf", "user.identity"],
    },
    "ods_gnb_alarm": {
        "category_path": ["源数据", "配置"],
        "category_code": "source-data.config",
        "tags": ["ODS", "BBU", "电源", "机房", "质量"],
        "tag_codes": ["layer.ods", "equipment.bbu", "equipment.power", "equipment.machine-room", "network.quality"],
    },
    "dwd_session_qos": {
        "category_path": ["网络", "质量"],
        "category_code": "network.quality",
        "tags": ["DWD", "速率", "时延", "丢包", "保持", "标识信息"],
        "tag_codes": ["layer.dwd", "network.rate", "network.latency", "network.packet-loss", "network.retain", "user.identity"],
    },
    "dwd_ho_event": {
        "category_path": ["网络", "移动"],
        "category_code": "network.mobility",
        "tags": ["DWD", "保持", "接入", "质量", "标识信息"],
        "tag_codes": ["layer.dwd", "network.retain", "network.access", "network.quality", "user.identity"],
    },
    "dws_cell_hourly": {
        "category_path": ["网络", "覆盖"],
        "category_code": "network.coverage",
        "tags": ["DWS", "覆盖", "话务", "速率", "保持", "质量"],
        "tag_codes": ["layer.dws", "network.coverage", "network.traffic", "network.rate", "network.retain", "network.quality"],
    },
    "dws_area_traffic": {
        "category_path": ["网络", "话务"],
        "category_code": "network.traffic",
        "tags": ["DWS", "容量", "速率", "时延", "活动信息"],
        "tag_codes": ["layer.dws", "network.capacity", "network.rate", "network.latency", "user.activity"],
    },
    "ads_cell_profile": {
        "category_path": ["网络", "覆盖"],
        "category_code": "network.coverage",
        "tags": ["ADS", "覆盖", "容量", "质量", "射频"],
        "tag_codes": ["layer.ads", "network.coverage", "network.capacity", "network.quality", "equipment.rf"],
    },
    "ads_neighbor_pair": {
        "category_path": ["网络", "移动"],
        "category_code": "network.mobility",
        "tags": ["ADS", "保持", "质量", "工参"],
        "tag_codes": ["layer.ads", "network.retain", "network.quality", "source.engineering"],
    },
    "eval_user_score": {
        "category_path": ["用户", "业务信息"],
        "category_code": "user.service",
        "tags": ["EVAL", "覆盖", "移动", "业务信息", "活动信息"],
        "tag_codes": ["layer.eval", "network.coverage", "network.mobility", "user.service", "user.activity"],
    },
    "eval_net_health": {
        "category_path": ["网络", "质量"],
        "category_code": "network.quality",
        "tags": ["EVAL", "话务", "机房", "业务信息"],
        "tag_codes": ["layer.eval", "network.traffic", "equipment.machine-room", "user.service"],
    },
}


SEED_TABLES: list[dict] = [
    # ---- L1 ODS ----
    {
        "name": "ods_ue_signal",
        "layer": "ODS",
        "storage_type": "KAFKA",
        "description": "UE 信号采样原始流",
        "fields": [
            {"name": "imsi",      "type": "STRING",    "nullable": False, "partition": False, "description": "用户标识 (PII)"},
            {"name": "cell_id",   "type": "STRING",    "nullable": False, "partition": False, "description": "小区标识"},
            {"name": "rsrp",      "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "参考信号接收功率 (dBm), 值域 [-140,-44]"},
            {"name": "rsrq",      "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "参考信号接收质量 (dB)"},
            {"name": "sinr",      "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "信噪比 (dB), 值域 [-20,30]"},
            {"name": "timestamp", "type": "TIMESTAMP", "nullable": False, "partition": True,  "description": "采样时刻"},
        ],
    },
    {
        "name": "ods_gnb_alarm",
        "layer": "ODS",
        "storage_type": "KAFKA",
        "description": "基站告警原始流",
        "fields": [
            {"name": "gnb_id",     "type": "STRING",    "nullable": False, "partition": False, "description": "基站标识"},
            {"name": "alarm_type", "type": "STRING",    "nullable": False, "partition": False, "description": "告警类型枚举"},
            {"name": "severity",   "type": "INT",       "nullable": False, "partition": False, "description": "严重度 1..5"},
            {"name": "alarm_time", "type": "TIMESTAMP", "nullable": False, "partition": True,  "description": "告警时刻"},
            {"name": "duration",   "type": "BIGINT",    "nullable": True,  "partition": False, "description": "持续秒数"},
        ],
    },
    # ---- L2 DWD ----
    {
        "name": "dwd_session_qos",
        "layer": "DWD",
        "storage_type": "HIVE",
        "description": "会话级 QoS 明细",
        "fields": [
            {"name": "session_id",  "type": "STRING", "nullable": False, "partition": False, "description": "会话标识"},
            {"name": "imsi",        "type": "STRING", "nullable": False, "partition": False, "description": "用户标识",
             "expression": "passthrough", "_upstream": [("ods_ue_signal", "imsi")]},
            {"name": "avg_rsrp",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "会话平均 RSRP",
             "expression": "AVG(rsrp)", "_upstream": [("ods_ue_signal", "rsrp")]},
            {"name": "avg_rsrq",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "会话平均 RSRQ",
             "expression": "AVG(rsrq)", "_upstream": [("ods_ue_signal", "rsrq")]},
            {"name": "avg_sinr",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "会话平均 SINR",
             "expression": "AVG(sinr)", "_upstream": [("ods_ue_signal", "sinr")]},
            {"name": "packet_loss", "type": "DOUBLE", "nullable": True,  "partition": False, "description": "丢包率"},
            {"name": "latency",     "type": "DOUBLE", "nullable": True,  "partition": False, "description": "端到端时延 (ms)"},
            {"name": "throughput",  "type": "DOUBLE", "nullable": True,  "partition": False, "description": "吞吐量 (Mbps)"},
            {"name": "drop_flag",   "type": "INT",    "nullable": False, "partition": False, "description": "掉话标记 0/1"},
        ],
    },
    {
        "name": "dwd_ho_event",
        "layer": "DWD",
        "storage_type": "HIVE",
        "description": "切换事件明细",
        "fields": [
            {"name": "imsi",        "type": "STRING", "nullable": False, "partition": False, "description": "用户标识",
             "expression": "passthrough", "_upstream": [("ods_ue_signal", "imsi")]},
            {"name": "source_cell", "type": "STRING", "nullable": False, "partition": False, "description": "源小区",
             "expression": "passthrough", "_upstream": [("ods_ue_signal", "cell_id")]},
            {"name": "target_cell", "type": "STRING", "nullable": False, "partition": False, "description": "目标小区"},
            {"name": "ho_type",     "type": "STRING", "nullable": False, "partition": False, "description": "切换类型"},
            {"name": "ho_result",   "type": "STRING", "nullable": False, "partition": False, "description": "SUCCESS/FAIL"},
            {"name": "ho_cause",    "type": "STRING", "nullable": True,  "partition": False, "description": "失败原因"},
            {"name": "ho_latency",  "type": "DOUBLE", "nullable": True,  "partition": False, "description": "切换时延 (ms)"},
        ],
    },
    # ---- L3 DWS ----
    {
        "name": "dws_cell_hourly",
        "layer": "DWS",
        "storage_type": "HIVE",
        "description": "小区小时粒度汇总指标",
        "fields": [
            {"name": "cell_id",         "type": "STRING",    "nullable": False, "partition": False, "description": "小区标识",
             "expression": "passthrough", "_upstream": [("dwd_session_qos", "imsi")]},
            {"name": "hour_bucket",     "type": "TIMESTAMP", "nullable": False, "partition": True,  "description": "小时窗口起点"},
            {"name": "avg_rsrp",        "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "小时均 RSRP",
             "expression": "AVG(rsrp)", "_upstream": [("dwd_session_qos", "avg_rsrp")]},
            {"name": "avg_sinr",        "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "小时均 SINR",
             "expression": "AVG(sinr)", "_upstream": [("dwd_session_qos", "avg_sinr")]},
            {"name": "total_sessions",  "type": "BIGINT",    "nullable": True,  "partition": False, "description": "会话数",
             "expression": "COUNT(DISTINCT session_id)", "_upstream": [("dwd_session_qos", "session_id")]},
            {"name": "drop_rate",       "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "掉话率",
             "expression": "SUM(drop_flag)/COUNT(*)", "_upstream": [("dwd_session_qos", "drop_flag")]},
            {"name": "avg_throughput",  "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "平均吞吐",
             "expression": "AVG(throughput)", "_upstream": [("dwd_session_qos", "throughput")]},
            {"name": "ho_success_rate", "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "切换成功率",
             "expression": "AVG(CASE WHEN ho_result='SUCCESS' THEN 1 ELSE 0 END)",
             "_upstream": [("dwd_ho_event", "ho_result")]},
        ],
    },
    {
        "name": "dws_area_traffic",
        "layer": "DWS",
        "storage_type": "HIVE",
        "description": "区域小时流量汇总",
        "fields": [
            {"name": "area_id",          "type": "STRING",    "nullable": False, "partition": False, "description": "区域标识"},
            {"name": "hour_bucket",      "type": "TIMESTAMP", "nullable": False, "partition": True,  "description": "小时窗口"},
            {"name": "total_throughput", "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "总吞吐",
             "expression": "SUM(throughput)", "_upstream": [("dwd_session_qos", "throughput")]},
            {"name": "active_users",     "type": "BIGINT",    "nullable": True,  "partition": False, "description": "活跃用户",
             "expression": "COUNT(DISTINCT imsi)", "_upstream": [("dwd_session_qos", "imsi")]},
            {"name": "avg_latency",      "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "平均时延",
             "expression": "AVG(latency)", "_upstream": [("dwd_session_qos", "latency")]},
            {"name": "peak_throughput",  "type": "DOUBLE",    "nullable": True,  "partition": False, "description": "峰值吞吐",
             "expression": "MAX(throughput)", "_upstream": [("dwd_session_qos", "throughput")]},
        ],
    },
    # ---- L4 ADS ----
    {
        "name": "ads_cell_profile",
        "layer": "ADS",
        "storage_type": "STARROCKS",
        "description": "小区日画像 KPI",
        "fields": [
            {"name": "cell_id",         "type": "STRING", "nullable": False, "partition": False, "description": "小区标识",
             "expression": "passthrough", "_upstream": [("dws_cell_hourly", "cell_id")]},
            {"name": "date",            "type": "DATE",   "nullable": False, "partition": True,  "description": "日期"},
            {"name": "coverage_score",  "type": "DOUBLE", "nullable": True,  "partition": False, "description": "覆盖得分 0-100",
             "expression": "weighted(avg_rsrp)", "_upstream": [("dws_cell_hourly", "avg_rsrp")]},
            {"name": "capacity_score",  "type": "DOUBLE", "nullable": True,  "partition": False, "description": "容量得分",
             "expression": "weighted(avg_throughput)", "_upstream": [("dws_cell_hourly", "avg_throughput")]},
            {"name": "stability_score", "type": "DOUBLE", "nullable": True,  "partition": False, "description": "稳定性得分",
             "expression": "1 - drop_rate", "_upstream": [("dws_cell_hourly", "drop_rate")]},
            {"name": "composite_kpi",   "type": "DOUBLE", "nullable": True,  "partition": False, "description": "复合 KPI",
             "expression": "0.4*coverage_score + 0.3*capacity_score + 0.3*stability_score"},
        ],
    },
    {
        "name": "ads_neighbor_pair",
        "layer": "ADS",
        "storage_type": "STARROCKS",
        "description": "邻区切换对统计",
        "fields": [
            {"name": "source_cell",        "type": "STRING", "nullable": False, "partition": False, "description": "源小区",
             "expression": "passthrough", "_upstream": [("dwd_ho_event", "source_cell")]},
            {"name": "target_cell",        "type": "STRING", "nullable": False, "partition": False, "description": "目标小区",
             "expression": "passthrough", "_upstream": [("dwd_ho_event", "target_cell")]},
            {"name": "ho_count",           "type": "BIGINT", "nullable": True,  "partition": False, "description": "切换次数",
             "expression": "COUNT(*)", "_upstream": [("dwd_ho_event", "ho_result")]},
            {"name": "ho_success_rate",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "切换成功率",
             "expression": "AVG(CASE WHEN ho_result='SUCCESS' THEN 1 ELSE 0 END)",
             "_upstream": [("dwd_ho_event", "ho_result")]},
            {"name": "avg_ho_latency",     "type": "DOUBLE", "nullable": True,  "partition": False, "description": "平均切换时延",
             "expression": "AVG(ho_latency)", "_upstream": [("dwd_ho_event", "ho_latency")]},
            {"name": "recommend_priority", "type": "INT",    "nullable": True,  "partition": False, "description": "邻区优先级建议"},
        ],
    },
    # ---- L5 EVAL ----
    {
        "name": "eval_user_score",
        "layer": "EVAL",
        "storage_type": "STARROCKS",
        "description": "用户日 QoE 评分",
        "fields": [
            {"name": "imsi",               "type": "STRING", "nullable": False, "partition": False, "description": "用户标识"},
            {"name": "date",               "type": "DATE",   "nullable": False, "partition": True,  "description": "日期"},
            {"name": "qoe_score",          "type": "DOUBLE", "nullable": True,  "partition": False, "description": "复合 QoE 评分 0-100",
             "expression": "0.5*signal_quality + 0.3*mobility_score + 0.2*service_continuity"},
            {"name": "signal_quality",     "type": "DOUBLE", "nullable": True,  "partition": False, "description": "信号质量分量",
             "expression": "f(coverage_score)", "_upstream": [("ads_cell_profile", "coverage_score")]},
            {"name": "mobility_score",     "type": "DOUBLE", "nullable": True,  "partition": False, "description": "移动性分量",
             "expression": "f(capacity_score)", "_upstream": [("ads_cell_profile", "capacity_score")]},
            {"name": "service_continuity", "type": "DOUBLE", "nullable": True,  "partition": False, "description": "业务连续性分量",
             "expression": "f(stability_score)", "_upstream": [("ads_cell_profile", "stability_score")]},
        ],
    },
    {
        "name": "eval_net_health",
        "layer": "EVAL",
        "storage_type": "STARROCKS",
        "description": "区域日网络健康指数",
        "fields": [
            {"name": "area_id",                 "type": "STRING", "nullable": False, "partition": False, "description": "区域标识"},
            {"name": "date",                    "type": "DATE",   "nullable": False, "partition": True,  "description": "日期"},
            {"name": "health_index",            "type": "DOUBLE", "nullable": True,  "partition": False, "description": "健康指数",
             "expression": "0.5*(1-alarm_severity_weighted) + 0.5*health_from_qoe"},
            {"name": "alarm_severity_weighted", "type": "DOUBLE", "nullable": True,  "partition": False, "description": "加权告警严重度",
             "expression": "SUM(severity*duration)", "_upstream": [("ods_gnb_alarm", "severity"), ("ods_gnb_alarm", "duration")]},
            {"name": "user_complaint_ratio",    "type": "DOUBLE", "nullable": True,  "partition": False, "description": "用户投诉比",
             "expression": "f(qoe_score)", "_upstream": [("eval_user_score", "qoe_score")]},
            {"name": "degradation_trend",       "type": "DOUBLE", "nullable": True,  "partition": False, "description": "退化趋势",
             "expression": "trend(total_throughput)", "_upstream": [("dws_area_traffic", "total_throughput")]},
        ],
    },
]


def _derive_lineage() -> list[dict]:
    """Flatten the _upstream hints embedded in each field into explicit edges."""
    edges: list[dict] = []
    for tbl in SEED_TABLES:
        for field in tbl["fields"]:
            for upstream_table, upstream_field in field.get("_upstream", []):
                edges.append({
                    "from_table": upstream_table,
                    "from_field": upstream_field,
                    "to_table": tbl["name"],
                    "to_field": field["name"],
                    "transform_expr": field.get("expression", "passthrough"),
                })
    return edges


SEED_LINEAGE: list[dict] = _derive_lineage()
