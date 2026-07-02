from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import pipeline
from backend.metadata.models import TableSummary


def test_pipeline_aggregates_table_edges(monkeypatch):
    monkeypatch.setattr(
        pipeline.service,
        "list_tables",
        lambda: [
            TableSummary(
                id="t1",
                name="ods_ue_signal",
                layer="ODS",
                layer_priority=1,
                storage_type="KAFKA",
                description="raw signal",
                field_count=2,
            ),
            TableSummary(
                id="t2",
                name="dwd_session_qos",
                layer="DWD",
                layer_priority=2,
                storage_type="HIVE",
                description="session qos",
                field_count=3,
            ),
            TableSummary(
                id="t3",
                name="dws_cell_hourly",
                layer="DWS",
                layer_priority=3,
                storage_type="HIVE",
                description="cell hourly",
                field_count=4,
            ),
            TableSummary(
                id="t4",
                name="ads_cell_profile",
                layer="ADS",
                layer_priority=4,
                storage_type="STARROCKS",
                description="cell profile",
                field_count=5,
            ),
            TableSummary(
                id="t5",
                name="unrelated_table",
                layer="ODS",
                layer_priority=1,
                storage_type="KAFKA",
                description="unrelated",
                field_count=1,
            ),
        ],
    )
    monkeypatch.setattr(
        pipeline,
        "run_query",
        lambda *_args, **_kwargs: [
            {"source": "ods_ue_signal", "target": "dwd_session_qos", "weight": 2, "fields": ["avg_rsrp"]},
            {"source": "dwd_session_qos", "target": "dws_cell_hourly", "weight": 3, "fields": ["avg_rsrp", "avg_sinr"]},
            {"source": "dws_cell_hourly", "target": "ads_cell_profile", "weight": 1, "fields": ["coverage_score"]},
            {"source": "unrelated_table", "target": "ads_cell_profile", "weight": 1, "fields": ["noise"]},
        ],
    )

    app = FastAPI()
    app.include_router(pipeline.router)
    res = TestClient(app).get("/api/pipeline?table=dws_cell_hourly&depth=2")

    assert res.status_code == 200
    payload = res.json()
    assert payload["mode"] == "forward"
    assert payload["depth"] == 2
    assert payload["selected_path"] == ["ods_ue_signal", "dwd_session_qos", "dws_cell_hourly"]
    assert payload["constraints"] == []
    assert {node["name"] for node in payload["nodes"]} == {
        "ods_ue_signal",
        "dwd_session_qos",
        "dws_cell_hourly",
        "ads_cell_profile",
    }
    selected = next(node for node in payload["nodes"] if node["name"] == "dws_cell_hourly")
    assert selected["selected"] is True
    assert selected["upstream_tables"] == ["dwd_session_qos"]
    assert selected["downstream_tables"] == ["ads_cell_profile"]
    assert payload["edges"] == [
        {
            "source": "ods_ue_signal",
            "target": "dwd_session_qos",
            "weight": 2,
            "fields": ["avg_rsrp"],
            "constraint_summary": "",
        },
        {
            "source": "dwd_session_qos",
            "target": "dws_cell_hourly",
            "weight": 3,
            "fields": ["avg_rsrp", "avg_sinr"],
            "constraint_summary": "",
        },
        {
            "source": "dws_cell_hourly",
            "target": "ads_cell_profile",
            "weight": 1,
            "fields": ["coverage_score"],
            "constraint_summary": "",
        },
    ]


def test_pipeline_reverse_mode_flips_edges(monkeypatch):
    monkeypatch.setattr(
        pipeline.service,
        "list_tables",
        lambda: [
            TableSummary(
                id="ads",
                name="ads_cell_profile",
                layer="ADS",
                layer_priority=4,
                storage_type="STARROCKS",
                description="cell profile",
                field_count=3,
            ),
            TableSummary(
                id="eval",
                name="eval_user_score",
                layer="EVAL",
                layer_priority=5,
                storage_type="STARROCKS",
                description="user score",
                field_count=2,
            ),
        ],
    )
    monkeypatch.setattr(
        pipeline,
        "run_query",
        lambda *_args, **_kwargs: [
            {
                "source": "ads_cell_profile",
                "target": "eval_user_score",
                "weight": 2,
                "fields": ["coverage_score", "capacity_score"],
            }
        ],
    )

    app = FastAPI()
    app.include_router(pipeline.router)
    res = TestClient(app).get("/api/pipeline?mode=reverse&table=eval_user_score&depth=3")

    assert res.status_code == 200
    payload = res.json()
    assert payload["selected_path"] == ["ads_cell_profile", "eval_user_score"]
    assert payload["edges"] == [
        {
            "source": "eval_user_score",
            "target": "ads_cell_profile",
            "weight": 2,
            "fields": ["coverage_score", "capacity_score"],
            "constraint_summary": "coverage_score in [0,100]; capacity_score in [0,100]",
        }
    ]
    assert payload["constraints"] == [
        {"field": "coverage_score", "range": [80, 100], "rows": 3, "bucket": "excellent"},
        {"field": "capacity_score", "range": [50, 80], "rows": 4, "bucket": "normal"},
    ]
