"""P1-5 (Neo4j part): MATCH (t:Table) RETURN count(t) == 10 after seeding."""
import pytest

from backend.metadata.graph import run_query


@pytest.mark.infra
def test_p1_5_table_count_is_ten():
    rows = run_query("MATCH (t:Table) RETURN count(t) AS n")
    assert rows[0]["n"] == 10


@pytest.mark.infra
def test_field_count_around_seventy():
    rows = run_query("MATCH (f:Field) RETURN count(f) AS n")
    assert 60 <= rows[0]["n"] <= 80


@pytest.mark.infra
def test_has_field_edges_cover_all_fields():
    rows = run_query("""
        MATCH (t:Table)-[:HAS_FIELD]->(f:Field)
        RETURN count(*) AS n
    """)
    field_total = run_query("MATCH (f:Field) RETURN count(f) AS n")[0]["n"]
    assert rows[0]["n"] == field_total


@pytest.mark.infra
def test_derives_from_edges_present():
    rows = run_query("""
        MATCH ()-[r:DERIVES_FROM]->()
        RETURN count(r) AS n
    """)
    assert rows[0]["n"] >= 30
