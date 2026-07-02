from backend.metadata import service
from backend.metadata.models import LineageEdgeCreateRequest


def test_create_lineage_edge_merges_existing_relationship_and_returns_normalized_edge(monkeypatch):
    calls = []

    def fake_run_query(cypher: str, **params):
        calls.append((cypher, params))
        if "RETURN from_f.id AS source_field_id" in cypher:
            return [{"source_field_id": "source-field", "target_field_id": "target-field"}]
        if "MATCH p = (source:Field" in cypher:
            return []
        if "MERGE (to_f)-[r:DERIVES_FROM]->(from_f)" in cypher:
            return [{"edge_id": "existing-edge"}]
        if "WHERE r.edge_id = $edge_id OR elementId(r) = $edge_id" in cypher:
            return [{
                "edge_id": params["edge_id"],
                "from_table": "source_table",
                "from_field": "source_field",
                "to_table": "target_table",
                "to_field": "target_field",
                "transform_expr": "source_field + 1",
                "created_at": "2026-07-02T12:00:00Z",
            }]
        return []

    monkeypatch.setattr(service, "run_query", fake_run_query)

    edge = service.create_lineage_edge(LineageEdgeCreateRequest(
        from_table="source_table",
        from_field="source_field",
        to_table="target_table",
        to_field="target_field",
        transform_expr="source_field + 1",
    ))

    merge_cypher = next(cypher for cypher, _params in calls if "DERIVES_FROM" in cypher and "MERGE" in cypher)
    assert "CREATE (to_f)-[r:DERIVES_FROM" not in merge_cypher
    assert "MERGE (to_f)-[r:DERIVES_FROM]->(from_f)" in merge_cypher
    assert "ON CREATE SET" in merge_cypher
    assert "ON MATCH SET r.transform_expr = $transform_expr" in merge_cypher
    assert edge.edge_id == "existing-edge"
    assert edge.from_table == "source_table"
    assert edge.from_field == "source_field"
    assert edge.to_table == "target_table"
    assert edge.to_field == "target_field"
    assert edge.transform_expr == "source_field + 1"
