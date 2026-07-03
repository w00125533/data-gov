import { describe, expect, test } from 'vitest'
import type { Node } from '@antv/x6'
import type { LineageGraphResponse } from '../../api/client'
import {
  buildLineageX6GraphData,
  edgeKey,
  fieldEdgeCellId,
  fieldPortId,
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
})
