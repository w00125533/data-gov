"""P1-5b: SHOW CONSTRAINTS returns >= 4; SHOW INDEXES returns >= 3 expected indexes."""
import pytest

from backend.metadata.graph import run_query


@pytest.mark.infra
def test_p1_5b_constraints_exist():
    rows = run_query("SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties")
    names = {r["name"] for r in rows}
    required = {"table_id_unique", "table_name_unique", "field_id_unique", "change_id_unique"}
    missing = required - names
    assert not missing, f"missing constraints: {missing}; got: {names}"


@pytest.mark.infra
def test_p1_5b_indexes_exist():
    rows = run_query("SHOW INDEXES YIELD name, labelsOrTypes, properties, type WHERE type <> 'LOOKUP'")
    names = {r["name"] for r in rows}
    required = {"field_name_idx", "change_changed_at_idx", "change_table_name_idx"}
    missing = required - names
    assert not missing, f"missing indexes: {missing}; got: {names}"
