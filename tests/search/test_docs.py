"""tests/search/test_docs.py"""
import pytest

from backend.search.docs import (
    SearchDoc,
    build_field_text,
    build_table_text,
    build_docs_from_neo4j,
)
from backend.seed.tables import SEED_TABLES


def test_build_table_text_includes_table_name_and_description_and_field_names():
    t = next(t for t in SEED_TABLES if t["name"] == "dws_cell_hourly")
    text = build_table_text(t)
    assert "dws_cell_hourly" in text
    # 描述、所有字段名都被拼进来
    for f in t["fields"]:
        assert f["name"] in text


def test_build_field_text_contains_type_and_description():
    t = next(t for t in SEED_TABLES if t["name"] == "ods_ue_signal")
    f = next(f for f in t["fields"] if f["name"] == "rsrp")
    text = build_field_text(t["name"], f)
    assert "rsrp" in text
    assert "DOUBLE" in text
    assert "参考信号接收功率" in text


def test_search_doc_ids_are_namespaced():
    t = SEED_TABLES[0]
    docs = build_docs_from_neo4j(seed_only=True)  # 走 in-memory fallback for unit test
    ids = {d.id for d in docs}
    assert f"table:{t['name']}" in ids
    assert any(i.startswith("field:") for i in ids)


@pytest.mark.infra
def test_build_docs_from_neo4j_returns_10_tables_and_about_65_fields():
    """需要 shared infra + Neo4j seeded."""
    docs = build_docs_from_neo4j()
    tables = [d for d in docs if d.type == "table"]
    fields = [d for d in docs if d.type == "field"]
    assert len(tables) == 10
    assert 60 <= len(fields) <= 80
    # 每条 doc 有非空 text 和 metadata.version
    for d in docs:
        assert d.text.strip()
        assert d.metadata.get("version", 0) >= 1
