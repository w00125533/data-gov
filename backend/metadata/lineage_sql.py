"""SQL preview and import helpers for lineage metadata."""
from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp, parse_one

from backend.metadata.models import (
    EdgeChangePreview,
    FieldChangePreview,
    LineageEdge,
    LineageSqlImportPreviewResponse,
    UpstreamRef,
)


class UnsupportedSqlError(ValueError):
    """Raised when SQL is outside the simple import-preview scope."""


@dataclass(frozen=True)
class SqlPreview:
    sql: str
    complete: bool
    warnings: list[str]


def generate_select_sql(
    table: str,
    fields: list[str],
    saved_sql: str | None,
    edges: list[LineageEdge],
) -> tuple[str, bool, list[str]]:
    edge_by_field = {edge.to_field: edge for edge in edges}
    group_by = _group_by_fields(edges)
    group_by_set = set(group_by)
    warnings: list[str] = []
    select_parts: list[str] = []
    source_tables = _source_tables_in_edge_order(edges)

    if len(set(source_tables)) > 1:
        warnings.append(
            "Unsupported multiple upstream tables for SQL preview: "
            f"{', '.join(sorted(set(source_tables)))}"
        )
        return _placeholder_sql(source_tables[0] if source_tables else table), False, warnings

    for field in fields:
        edge = edge_by_field.get(field)
        if edge is not None:
            expression = edge.transform_expr or edge.from_field
            select_parts.append(f"{expression} AS {field}")
        elif field in group_by_set:
            select_parts.append(field)
        else:
            warnings.append(f"Unable to generate SQL for field {field}: no upstream lineage edge")

    if not select_parts:
        warnings.append("Generated placeholder SQL because no selectable expressions were available")
        return _placeholder_sql(source_tables[0] if source_tables else table), False, warnings

    from_clause = source_tables[0] if source_tables else table
    sql = f"SELECT {', '.join(select_parts)} FROM {from_clause}"
    if group_by:
        sql = f"{sql} GROUP BY {', '.join(group_by)}"

    return sql, not warnings, warnings


def parse_select_preview(target_table: str, sql: str) -> LineageSqlImportPreviewResponse:
    statement = parse_one(sql, read="hive")
    source_table = _validate_simple_select(statement)

    aliases = _source_aliases(source_table)
    warnings: list[str] = []
    fields: list[FieldChangePreview] = []
    edges: list[EdgeChangePreview] = []

    for select_expression in statement.expressions:
        target_field = select_expression.alias_or_name
        expression = _select_expression(select_expression)
        expression_sql = select_expression.sql(dialect="hive")
        transform_expr = expression.sql(dialect="hive")
        upstream_refs: list[UpstreamRef] = []
        calc_type = _calc_type(expression)

        for column in expression.find_all(exp.Column):
            source_table = _resolve_column_table(column, aliases)
            if source_table is None:
                if column.table:
                    warnings.append(
                        f"Unable to resolve table alias {column.table} for field {target_field}"
                    )
                continue

            upstream_refs.append(UpstreamRef(table=source_table, field=column.name))
            edges.append(EdgeChangePreview(
                action="add",
                edge=LineageEdge(
                    from_table=source_table,
                    from_field=column.name,
                    to_table=target_table,
                    to_field=target_field,
                    transform_expr=transform_expr,
                    calc_type=calc_type,
                    calc_params={},
                ),
            ))

        fields.append(FieldChangePreview(
            action="add",
            field=target_field,
            expression=expression_sql,
            upstream=upstream_refs,
        ))

    return LineageSqlImportPreviewResponse(
        table=target_table,
        sql=sql,
        fields=fields,
        edges=edges,
        warnings=warnings,
    )


def _group_by_fields(edges: list[LineageEdge]) -> list[str]:
    grouped: list[str] = []
    for edge in sorted(edges, key=lambda item: (item.to_field, item.edge_id)):
        values = edge.calc_params.get("group_by") if edge.calc_params else None
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value not in grouped:
                grouped.append(value)
    return grouped


def _source_tables_in_edge_order(edges: list[LineageEdge]) -> list[str]:
    source_tables: list[str] = []
    for edge in edges:
        if edge.from_table and edge.from_table not in source_tables:
            source_tables.append(edge.from_table)
    return source_tables


def _placeholder_sql(source_table: str) -> str:
    return f"SELECT\n  NULL AS placeholder\nFROM {source_table}"


def _validate_simple_select(statement: exp.Expression) -> exp.Table:
    if isinstance(statement, exp.SetOperation):
        raise UnsupportedSqlError("Unsupported SQL shape: set operation is not supported")
    if not isinstance(statement, exp.Select):
        raise UnsupportedSqlError("only SELECT statements are supported")
    if statement.args.get("with_") is not None:
        raise UnsupportedSqlError("Unsupported SQL shape: CTE is not supported")
    if list(statement.find_all(exp.Subquery)):
        raise UnsupportedSqlError("Unsupported SQL shape: subquery is not supported")

    joins = statement.args.get("joins") or []
    if joins:
        if all((join.args.get("kind") or "").upper() == "CROSS" for join in joins):
            raise UnsupportedSqlError("Unsupported SQL shape: multiple source tables are not supported")
        raise UnsupportedSqlError("Unsupported SQL shape: JOIN is not supported")

    from_clause = statement.args.get("from_")
    source = from_clause.this if from_clause is not None else None
    if not isinstance(source, exp.Table):
        raise UnsupportedSqlError("Unsupported SQL shape: one top-level FROM source table is required")

    return source


def _source_aliases(source_table: exp.Table) -> dict[str, str]:
    table_name = source_table.name
    return {
        table_name: table_name,
        source_table.alias_or_name: table_name,
    }


def _select_expression(select_expression: exp.Expression) -> exp.Expression:
    if isinstance(select_expression, exp.Alias):
        return select_expression.this
    return select_expression


def _calc_type(expression: exp.Expression) -> str:
    if list(expression.find_all(exp.Case)):
        return "CONDITION"
    if list(expression.find_all(exp.Window)):
        return "WINDOW"
    if list(expression.find_all(exp.AggFunc)):
        return "AGGREGATE"
    if isinstance(expression, exp.Column):
        return "DIRECT"
    if isinstance(expression, exp.Literal):
        return "CONSTANT"
    return "EXPRESSION"


def _resolve_column_table(column: exp.Column, aliases: dict[str, str]) -> str | None:
    if column.table:
        return aliases.get(column.table)
    source_tables = sorted(set(aliases.values()))
    if len(source_tables) == 1:
        return source_tables[0]
    return None
