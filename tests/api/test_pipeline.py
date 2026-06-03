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
        ],
    )
    monkeypatch.setattr(
        pipeline,
        "run_query",
        lambda *_args, **_kwargs: [{"source": "ods_ue_signal", "target": "dwd_session_qos", "weight": 2}],
    )

    app = FastAPI()
    app.include_router(pipeline.router)
    res = TestClient(app).get("/api/pipeline?table=dwd_session_qos")

    assert res.status_code == 200
    payload = res.json()
    assert payload["mode"] == "forward"
    assert payload["nodes"][1]["selected"] is True
    assert payload["edges"] == [{"source": "ods_ue_signal", "target": "dwd_session_qos", "weight": 2}]


def test_pipeline_reverse_mode_flips_edges(monkeypatch):
    monkeypatch.setattr(pipeline.service, "list_tables", lambda: [])
    monkeypatch.setattr(
        pipeline,
        "run_query",
        lambda *_args, **_kwargs: [{"source": "ods_ue_signal", "target": "dwd_session_qos", "weight": 2}],
    )

    app = FastAPI()
    app.include_router(pipeline.router)
    res = TestClient(app).get("/api/pipeline?mode=reverse")

    assert res.status_code == 200
    assert res.json()["edges"] == [{"source": "dwd_session_qos", "target": "ods_ue_signal", "weight": 2}]
