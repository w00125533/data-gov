import pytest

from backend.metadata import service
from backend.metadata.models import (
    FieldResponse,
    LineageEdge,
    LineageEdgeCreateRequest,
    LineageEdgeEndpointUpdateRequest,
    TableResponse,
)


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


def _table(name: str) -> TableResponse:
    return TableResponse(
        id=f"table-{name}",
        name=name,
        layer="DWS",
        layer_priority=3,
        storage_type="HIVE",
        description="",
        fields=[
            FieldResponse(
                id=f"field-{name}",
                name="metric",
                field_type="DOUBLE",
                is_nullable=True,
                is_partition=False,
                expression=None,
                description="",
                version=1,
                upstream=[],
            )
        ],
    )


def test_lineage_graph_keeps_separate_table_edges_for_mixed_traversal_directions(monkeypatch):
    def fake_get_table_by_name(name: str, optional: bool = False):
        return _table(name)

    def fake_get_lineage(table: str, direction: str, depth: int):
        assert table == "root_table"
        assert depth == 2
        if direction == "up":
            return [
                LineageEdge(
                    edge_id="edge-up",
                    from_table="shared_source",
                    from_field="metric",
                    to_table="shared_target",
                    to_field="up_metric",
                    transform_expr="up_metric",
                    calc_type="DIRECT",
                    calc_params={},
                )
            ]
        return [
            LineageEdge(
                edge_id="edge-down",
                from_table="shared_source",
                from_field="metric",
                to_table="shared_target",
                to_field="down_metric",
                transform_expr="down_metric",
                calc_type="AGGREGATE",
                calc_params={"function": "SUM"},
            )
        ]

    monkeypatch.setattr(service, "get_table_by_name", fake_get_table_by_name)
    monkeypatch.setattr(service, "get_lineage", fake_get_lineage)

    graph = service.get_lineage_graph(
        table="root_table",
        depth=2,
        include_upstream=True,
        include_downstream=True,
    )

    same_pair_edges = [
        edge for edge in graph.table_edges
        if edge.source == "shared_source" and edge.target == "shared_target"
    ]
    assert sorted(edge.direction for edge in same_pair_edges) == ["downstream", "upstream"]
    assert {edge.direction: edge.fields for edge in same_pair_edges} == {
        "upstream": ["up_metric"],
        "downstream": ["down_metric"],
    }


def test_update_lineage_edge_endpoints_preserves_original_edge_id(monkeypatch):
    calls = []

    current_edge = LineageEdge(
        edge_id="edge-original",
        from_table="old_source",
        from_field="old_metric",
        to_table="old_target",
        to_field="old_metric",
        transform_expr="metric + 1",
        calc_type="EXPRESSION",
        calc_params={"operator": "plus"},
        created_at="2026-07-03T09:00:00Z",
    )

    def fake_load_lineage_edge(edge_id: str):
        assert edge_id == "edge-original"
        return current_edge

    def fake_run_query(cypher: str, **params):
        calls.append((cypher, params))
        if "RETURN from_f.id AS source_field_id" in cypher:
            return [{"source_field_id": "new-source-field", "target_field_id": "new-target-field"}]
        if "old_r" in cypher and "DELETE old_r" in cypher:
            assert params["edge_id"] == "edge-original"
            return [{"edge_id": "edge-original", "conflict_edge_id": None}]
        return []

    def fake_create_lineage_edge(_req):
        return LineageEdge(
            edge_id="edge-new",
            from_table="new_source",
            from_field="metric",
            to_table="new_target",
            to_field="metric",
            transform_expr="metric + 1",
        )

    monkeypatch.setattr(service, "_load_lineage_edge", fake_load_lineage_edge)
    monkeypatch.setattr(service, "run_query", fake_run_query)
    monkeypatch.setattr(service, "assert_no_lineage_cycle", lambda **_kwargs: None)
    monkeypatch.setattr(service, "delete_lineage_edge", lambda edge_id: None)
    monkeypatch.setattr(service, "create_lineage_edge", fake_create_lineage_edge)

    edge = service.update_lineage_edge_endpoints(
        "edge-original",
        LineageEdgeEndpointUpdateRequest(
            from_table="new_source",
            from_field="metric",
            to_table="new_target",
            to_field="metric",
        ),
    )

    assert edge.edge_id == "edge-original"
    assert any("old_r" in cypher and "DELETE old_r" in cypher for cypher, _params in calls)


def test_update_lineage_edge_endpoints_passes_ignore_edge_to_cycle_check(monkeypatch):
    captured = {}
    current_edge = LineageEdge(
        edge_id="edge-cycle",
        from_table="old_source",
        from_field="metric",
        to_table="old_target",
        to_field="metric",
        transform_expr="metric + 1",
    )

    def fake_run_query(cypher: str, **params):
        if "RETURN from_f.id AS source_field_id" in cypher:
            return [{"source_field_id": "new-source-field", "target_field_id": "new-target-field"}]
        if "old_r" in cypher and "DELETE old_r" in cypher:
            return [{"edge_id": "edge-cycle", "conflict_edge_id": None}]
        return []

    def fake_assert_no_lineage_cycle(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(service, "_load_lineage_edge", lambda edge_id: current_edge)
    monkeypatch.setattr(service, "run_query", fake_run_query)
    monkeypatch.setattr(service, "assert_no_lineage_cycle", fake_assert_no_lineage_cycle)

    service.update_lineage_edge_endpoints(
        "edge-cycle",
        LineageEdgeEndpointUpdateRequest(
            from_table="new_source",
            from_field="metric",
            to_table="new_target",
            to_field="metric",
        ),
    )

    assert captured == {
        "target_field_id": "new-target-field",
        "source_field_id": "new-source-field",
        "ignore_edge_id": "edge-cycle",
    }


def test_assert_no_lineage_cycle_filters_ignored_edge_from_path_query(monkeypatch):
    captured = {}

    def fake_run_query(cypher: str, **params):
        captured["cypher"] = cypher
        captured["params"] = params
        return []

    monkeypatch.setattr(service, "run_query", fake_run_query)

    service.assert_no_lineage_cycle(
        target_field_id="target-field",
        source_field_id="source-field",
        ignore_edge_id="edge-ignore",
    )

    assert "ignore_edge_id" in captured["params"]
    assert captured["params"]["ignore_edge_id"] == "edge-ignore"
    assert "relationships(p)" in captured["cypher"]
    assert "edge_id" in captured["cypher"]
    assert "elementId" in captured["cypher"]


def test_update_lineage_edge_endpoints_does_not_write_stale_calc_metadata(monkeypatch):
    mutation = {}
    current_edge = LineageEdge(
        edge_id="edge-stale",
        from_table="old_source",
        from_field="metric",
        to_table="old_target",
        to_field="metric",
        transform_expr="stale expression",
        calc_type="EXPRESSION",
        calc_params={"stale": True},
    )

    def fake_run_query(cypher: str, **params):
        if "RETURN from_f.id AS source_field_id" in cypher:
            return [{"source_field_id": "new-source-field", "target_field_id": "new-target-field"}]
        if "old_r" in cypher and "DELETE old_r" in cypher:
            mutation["cypher"] = cypher
            mutation["params"] = params
            return [{"edge_id": "edge-stale", "conflict_edge_id": None}]
        return []

    monkeypatch.setattr(service, "_load_lineage_edge", lambda edge_id: current_edge)
    monkeypatch.setattr(service, "run_query", fake_run_query)
    monkeypatch.setattr(service, "assert_no_lineage_cycle", lambda **_kwargs: None)

    service.update_lineage_edge_endpoints(
        "edge-stale",
        LineageEdgeEndpointUpdateRequest(
            from_table="new_source",
            from_field="metric",
            to_table="new_target",
            to_field="metric",
        ),
    )

    assert "transform_expr" not in mutation["params"]
    assert "calc_type" not in mutation["params"]
    assert "calc_params" not in mutation["params"]
    assert "new_r.transform_expr" not in mutation["cypher"]
    assert "new_r.calc_type" not in mutation["cypher"]
    assert "new_r.calc_params" not in mutation["cypher"]


def test_update_lineage_edge_endpoints_uses_single_mutation_without_delete_or_create(monkeypatch):
    calls = []
    current_edge = LineageEdge(
        edge_id="edge-atomic",
        from_table="old_source",
        from_field="metric",
        to_table="old_target",
        to_field="metric",
        transform_expr="metric + 1",
        calc_type="EXPRESSION",
        calc_params={"operator": "plus"},
    )

    def fake_run_query(cypher: str, **params):
        calls.append((cypher, params))
        if "RETURN from_f.id AS source_field_id" in cypher:
            return [{"source_field_id": "new-source-field", "target_field_id": "new-target-field"}]
        if "old_r" in cypher and "DELETE old_r" in cypher:
            assert params["edge_id"] == "edge-atomic"
            return [{"edge_id": "edge-atomic", "conflict_edge_id": None}]
        return []

    monkeypatch.setattr(service, "_load_lineage_edge", lambda edge_id: current_edge)
    monkeypatch.setattr(service, "run_query", fake_run_query)
    monkeypatch.setattr(service, "assert_no_lineage_cycle", lambda **_kwargs: None)
    monkeypatch.setattr(
        service,
        "delete_lineage_edge",
        lambda _edge_id: (_ for _ in ()).throw(AssertionError("delete_lineage_edge must not be called")),
    )
    monkeypatch.setattr(
        service,
        "create_lineage_edge",
        lambda _req: (_ for _ in ()).throw(AssertionError("create_lineage_edge must not be called")),
    )

    edge = service.update_lineage_edge_endpoints(
        "edge-atomic",
        LineageEdgeEndpointUpdateRequest(
            from_table="new_source",
            from_field="metric",
            to_table="new_target",
            to_field="metric",
        ),
    )

    assert edge.edge_id == "edge-atomic"
    mutation_queries = [
        cypher for cypher, _params in calls
        if "old_r" in cypher and "DELETE old_r" in cypher
    ]
    assert len(mutation_queries) == 1


def test_update_lineage_edge_endpoints_raises_conflict_for_duplicate_destination(monkeypatch):
    assert hasattr(service, "LineageEndpointConflict")
    current_edge = LineageEdge(
        edge_id="edge-original",
        from_table="old_source",
        from_field="metric",
        to_table="old_target",
        to_field="metric",
        transform_expr="metric + 1",
    )

    def fake_run_query(cypher: str, **params):
        if "RETURN from_f.id AS source_field_id" in cypher:
            return [{"source_field_id": "new-source-field", "target_field_id": "new-target-field"}]
        if "old_r" in cypher and "DELETE old_r" in cypher:
            return [{"edge_id": None, "conflict_edge_id": "edge-existing"}]
        return []

    monkeypatch.setattr(service, "_load_lineage_edge", lambda edge_id: current_edge)
    monkeypatch.setattr(service, "run_query", fake_run_query)
    monkeypatch.setattr(service, "assert_no_lineage_cycle", lambda **_kwargs: None)

    with pytest.raises(service.LineageEndpointConflict) as exc:
        service.update_lineage_edge_endpoints(
            "edge-original",
            LineageEdgeEndpointUpdateRequest(
                from_table="new_source",
                from_field="metric",
                to_table="new_target",
                to_field="metric",
            ),
        )

    assert exc.value.edge_id == "edge-existing"


def test_graph_version_changes_when_edge_payload_changes_with_same_edge_id():
    before = service._graph_version([
        LineageEdge(
            edge_id="edge-stable",
            from_table="source",
            from_field="metric",
            to_table="target",
            to_field="metric",
            transform_expr="metric + 1",
            calc_type="EXPRESSION",
            calc_params={"operator": "plus"},
            updated_at="2026-07-03T10:00:00Z",
        )
    ])
    after = service._graph_version([
        LineageEdge(
            edge_id="edge-stable",
            from_table="source",
            from_field="metric",
            to_table="target",
            to_field="metric",
            transform_expr="metric + 2",
            calc_type="EXPRESSION",
            calc_params={"operator": "plus", "operand": 2},
            updated_at="2026-07-03T10:30:00Z",
        )
    ])

    assert before != after
