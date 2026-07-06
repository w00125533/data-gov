import { describe, expect, test } from 'vitest'
import type { Node } from '@antv/x6'
import type { LineageEdge, LineageGraphResponse } from '../../api/client'
import {
  buildLineageX6GraphData,
  edgeKey,
  fieldEdgeCellId,
  fieldPortId,
  safeCellId,
  tableEdgeCellId,
} from './lineageX6Adapter'

const payload: LineageGraphResponse = {
  root_table: 'dws_cell_hourly',
  depth: 2,
  include_upstream: true,
  include_downstream: true,
  graph_version: 'v-test',
  saved_sql: null,
  tables: [
    {
      id: 't-root',
      name: 'dws_cell_hourly',
      layer: 'DWS',
      layer_priority: 3,
      storage_type: 'HIVE',
      description: 'cell hourly',
      field_count: 2,
      sql_logic: null,
      sql_dialect: null,
      sql_source: null,
      sql_updated_at: '',
      fields: [
        {
          id: 'f-root-1',
          name: 'avg_rsrp',
          field_type: 'DOUBLE',
          is_nullable: true,
          is_partition: false,
          expression: 'AVG(q.avg_rsrp)',
          description: 'avg rsrp',
          version: 1,
          upstream: [],
        },
        {
          id: 'f-root-2',
          name: 'hour_bucket',
          field_type: 'TIMESTAMP',
          is_nullable: false,
          is_partition: true,
          expression: null,
          description: 'hour',
          version: 1,
          upstream: [],
        },
      ],
    },
    {
      id: 't-up',
      name: 'dwd_session_qos',
      layer: 'DWD',
      layer_priority: 2,
      storage_type: 'HIVE',
      description: 'qos',
      field_count: 2,
      sql_logic: null,
      sql_dialect: null,
      sql_source: null,
      sql_updated_at: '',
      fields: [
        {
          id: 'f-up-1',
          name: 'avg_rsrp',
          field_type: 'DOUBLE',
          is_nullable: true,
          is_partition: false,
          expression: null,
          description: 'avg rsrp',
          version: 1,
          upstream: [],
        },
        {
          id: 'f-up-2',
          name: 'hour_bucket',
          field_type: 'TIMESTAMP',
          is_nullable: false,
          is_partition: true,
          expression: null,
          description: 'hour',
          version: 1,
          upstream: [],
        },
      ],
    },
    {
      id: 't-down',
      name: 'ads_cell_profile',
      layer: 'ADS',
      layer_priority: 4,
      storage_type: 'STARROCKS',
      description: 'profile',
      field_count: 1,
      sql_logic: null,
      sql_dialect: null,
      sql_source: null,
      sql_updated_at: '',
      fields: [
        {
          id: 'f-down-1',
          name: 'coverage_score',
          field_type: 'DOUBLE',
          is_nullable: true,
          is_partition: false,
          expression: 'weighted(avg_rsrp)',
          description: 'coverage',
          version: 1,
          upstream: [],
        },
      ],
    },
  ],
  table_edges: [
    {
      source: 'dwd_session_qos',
      target: 'dws_cell_hourly',
      direction: 'upstream',
      field_edge_count: 1,
      calc_type_counts: { AGGREGATE: 1 },
      fields: ['avg_rsrp'],
    },
    {
      source: 'dws_cell_hourly',
      target: 'ads_cell_profile',
      direction: 'downstream',
      field_edge_count: 1,
      calc_type_counts: { DIRECT: 1 },
      fields: ['coverage_score'],
    },
  ],
  field_edges: [
    {
      edge_id: 'edge-1',
      from_table: 'dwd_session_qos',
      from_field: 'avg_rsrp',
      to_table: 'dws_cell_hourly',
      to_field: 'avg_rsrp',
      transform_expr: 'AVG(q.avg_rsrp)',
      calc_type: 'AGGREGATE',
      calc_params: { function: 'AVG' },
    },
    {
      edge_id: 'edge-2',
      from_table: 'dws_cell_hourly',
      from_field: 'avg_rsrp',
      to_table: 'ads_cell_profile',
      to_field: 'coverage_score',
      transform_expr: 'weighted(avg_rsrp)',
      calc_type: 'DIRECT',
      calc_params: {},
    },
  ],
}

function portIds(node?: Node.Metadata) {
  const ports = node?.ports
  if (!ports) return []
  return Array.isArray(ports) ? ports.map((port) => port.id) : ports.items?.map((port) => port.id)
}

function field(index: number) {
  return {
    id: `f-extra-${index}`,
    name: `metric_${index}`,
    field_type: 'DOUBLE',
    is_nullable: true,
    is_partition: false,
    expression: null,
    description: `metric ${index}`,
    version: 1,
    upstream: [],
  }
}

function tableBottom(node?: Node.Metadata) {
  return (node?.y ?? 0) + (node?.height ?? 0)
}

describe('lineageX6Adapter', () => {
  test('builds deterministic table nodes around the root table', () => {
    const graph = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(),
      selectedEdgeKey: undefined,
    })

    const root = graph.nodes.find((node) => node.id === 'dws_cell_hourly')
    const upstream = graph.nodes.find((node) => node.id === 'dwd_session_qos')
    const downstream = graph.nodes.find((node) => node.id === 'ads_cell_profile')

    expect(root?.x).toBe(520)
    expect(upstream?.x).toBeLessThan(root?.x ?? 0)
    expect(downstream?.x).toBeGreaterThan(root?.x ?? 0)
    expect(graph.edges.map((edge) => edge.id)).toContain(tableEdgeCellId('dwd_session_qos', 'dws_cell_hourly'))
  })

  test('uses built-in node shapes and stable table metadata', () => {
    const graph = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(['dws_cell_hourly']),
      selectedEdgeKey: undefined,
    })

    const root = graph.nodes.find((node) => node.id === 'dws_cell_hourly')
    const tableEdge = graph.edges.find((edge) => edge.id === tableEdgeCellId('dwd_session_qos', 'dws_cell_hourly'))

    expect(root?.shape).toBe('rect')
    expect(root?.data?.kind).toBe('table')
    expect(root?.data?.table.name).toBe('dws_cell_hourly')
    expect(root?.data?.expanded).toBe(true)
    expect(tableEdge?.data?.kind).toBe('table-edge')
    expect(tableEdge?.data?.edge.source).toBe('dwd_session_qos')
    expect(tableEdge?.data?.edge.target).toBe('dws_cell_hourly')
  })

  test('expanded tables expose stable field ports and dashed field edges', () => {
    const graph = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(['dwd_session_qos', 'dws_cell_hourly']),
      selectedEdgeKey: edgeKey(payload.field_edges[0]),
    })

    const upstream = graph.nodes.find((node) => node.id === 'dwd_session_qos')
    const root = graph.nodes.find((node) => node.id === 'dws_cell_hourly')
    const fieldEdge = graph.edges.find((item) => item.id === fieldEdgeCellId(payload.field_edges[0]))

    expect(portIds(upstream)).toContain(fieldPortId('out', 'avg_rsrp'))
    expect(portIds(root)).toContain(fieldPortId('in', 'avg_rsrp'))
    expect(fieldEdge?.source).toEqual({ cell: 'dwd_session_qos', port: fieldPortId('out', 'avg_rsrp') })
    expect(fieldEdge?.target).toEqual({ cell: 'dws_cell_hourly', port: fieldPortId('in', 'avg_rsrp') })
    expect(fieldEdge?.attrs?.line?.strokeDasharray).toBe('5 5')
    expect(fieldEdge?.attrs?.line?.stroke).toBe('#2563eb')
    expect(fieldEdge?.tools).toMatchObject([
      { name: 'source-arrowhead' },
      { name: 'target-arrowhead' },
    ])
    expect(fieldEdge?.data?.kind).toBe('field-edge')
    expect(fieldEdge?.data?.edge).toBe(payload.field_edges[0])
    expect(fieldEdge?.data?.lineageEdgeKey).toBe(edgeKey(payload.field_edges[0]))
    expect(edgeKey(payload.field_edges[0])).toBe('edge-1')
    expect(fieldEdgeCellId(payload.field_edges[0])).toBe('field-edge-s-edge-1')
  })

  test('field-level edges are hidden until a related table is expanded', () => {
    const collapsed = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(),
      selectedEdgeKey: undefined,
    })

    const expanded = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(['dws_cell_hourly']),
      selectedEdgeKey: undefined,
    })

    expect(collapsed.edges.some((item) => item.id === fieldEdgeCellId(payload.field_edges[0]))).toBe(false)
    expect(expanded.edges.some((item) => item.id === fieldEdgeCellId(payload.field_edges[0]))).toBe(true)
  })

  test('custom SVG text selectors do not inherit rect label positioning', () => {
    const graph = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(['dws_cell_hourly']),
      selectedEdgeKey: undefined,
    })

    const root = graph.nodes.find((node) => node.id === 'dws_cell_hourly')

    expect(root?.attrs?.title?.refX).toBeNull()
    expect(root?.attrs?.title?.refY).toBeNull()
    expect(root?.attrs?.title?.textAnchor).toBe('start')
    expect(root?.attrs?.toggleLabel?.refX).toBeNull()
    expect(root?.attrs?.toggleLabel?.refY).toBeNull()
    expect(root?.attrs?.toggleLabel?.textVerticalAnchor).toBe('middle')
    expect(root?.attrs?.fieldName0?.refX).toBeNull()
    expect(root?.attrs?.fieldName0?.textAnchor).toBe('start')
    expect(root?.attrs?.fieldType0?.textAnchor).toBe('end')
  })

  test('expanded stacked upstream tables are spaced by rendered node height', () => {
    const stackedPayload: LineageGraphResponse = {
      ...payload,
      tables: [
        payload.tables[0],
        {
          ...payload.tables[1],
          field_count: 9,
          fields: Array.from({ length: 9 }, (_, index) => field(index)),
        },
        {
          id: 't-up-2',
          name: 'ods_cell_signal',
          layer: 'ODS',
          layer_priority: 2,
          storage_type: 'HIVE',
          description: 'signal',
          field_count: 1,
          sql_logic: null,
          sql_dialect: null,
          sql_source: null,
          sql_updated_at: '',
          fields: [field(99)],
        },
      ],
      table_edges: [
        payload.table_edges[0],
        {
          source: 'ods_cell_signal',
          target: 'dws_cell_hourly',
          direction: 'upstream',
          field_edge_count: 1,
          calc_type_counts: { DIRECT: 1 },
          fields: ['metric_99'],
        },
      ],
      field_edges: [],
    }

    const graph = buildLineageX6GraphData({
      payload: stackedPayload,
      expandedTables: new Set(['dwd_session_qos']),
      selectedEdgeKey: undefined,
    })

    const expandedUpstream = graph.nodes.find((node) => node.id === 'dwd_session_qos')
    const nextUpstream = graph.nodes.find((node) => node.id === 'ods_cell_signal')

    expect(nextUpstream?.y ?? 0).toBeGreaterThanOrEqual(tableBottom(expandedUpstream) + 48)
  })

  test('encodes cell ids without punctuation collisions', () => {
    expect(safeCellId('db.table')).not.toBe(safeCellId('db_table'))
    expect(tableEdgeCellId('db.table', 'a-b')).not.toBe(tableEdgeCellId('db', 'table-a-b'))
    expect(tableEdgeCellId('a', 'b-s-c')).not.toBe(tableEdgeCellId('a-s-b', 'c'))
  })

  test('builds tuple-safe fallback field edge keys when backend edge ids are absent', () => {
    const left: LineageEdge = {
      from_table: 'a.b',
      from_field: 'c',
      to_table: 'x',
      to_field: 'y',
      transform_expr: 'p',
    }
    const right: LineageEdge = {
      from_table: 'a',
      from_field: 'b.c',
      to_table: 'x',
      to_field: 'y',
      transform_expr: 'p',
    }

    expect(edgeKey(left)).not.toBe(edgeKey(right))
    expect(fieldEdgeCellId(left)).not.toBe(fieldEdgeCellId(right))
  })
})
