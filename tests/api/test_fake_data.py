"""Unit tests for deterministic fake data generation."""
from __future__ import annotations

from backend.seed import fake_data


def test_eval_user_score_rows_cover_three_quality_bands():
    rows = fake_data._generate_eval_user_score_rows(rows=9)
    scores = [r["qoe_score"] for r in rows]

    assert any(s > 80 for s in scores)
    assert any(50 <= s <= 80 for s in scores)
    assert any(s < 50 for s in scores)


def test_generate_fake_data_eval_user_score_writes_hdfs_json(monkeypatch):
    calls = []

    def fake_write(table, rows):
        calls.append((table, rows))
        return "/tmp/sandbox/fake-data/eval_user_score.json"

    monkeypatch.setattr(fake_data, "_write_json_rows_to_hdfs", fake_write)

    result = fake_data.generate_fake_data(table="eval_user_score", rows=6)

    assert result["table"] == "eval_user_score"
    assert result["rows_written"] == 6
    assert result["hdfs_path"].endswith("eval_user_score.json")
    assert result["buckets"] == {"excellent": 2, "good": 2, "poor": 2}
    assert len(calls) == 1
    assert calls[0][0] == "eval_user_score"
    assert len(calls[0][1]) == 6
