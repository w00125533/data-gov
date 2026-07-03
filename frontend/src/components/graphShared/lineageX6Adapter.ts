import type { Edge, Node } from '@antv/x6'
import type { LineageEdge, LineageGraphResponse, LineageTableNode } from '../../api/client'
import { colorForLayer } from './palette'

export type LineageX6GraphInput = {
  payload?: LineageGraphResponse
  expandedTables: Set<string>
  selectedEdgeKey?: string
}

export type LineageX6GraphData = {
  nodes: Node.Metadata[]
  edges: Edge.Metadata[]
  fieldEdgeByCellId: Map<string, LineageEdge>
}

const NODE_WIDTH = 238
const COLLAPSED_HEIGHT = 76
const HEADER_HEIGHT = 48
const FIELD_ROW_HEIGHT = 28
const FIELD_TOP = 58
const CENTER_X = 520
const CENTER_Y = 260
const COLUMN_GAP = 320
const ROW_GAP = 190

type TablePosition = {
  x: number
  y: number
  side: 'upstream' | 'root' | 'downstream'
  level: number
}

export function edgeKey(edge: LineageEdge): string {
  return edge.edge_id || `${edge.from_table}.${edge.from_field}->${edge.to_table}.${edge.to_field}`
}

export function safeCellId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '_')
}

export function tableEdgeCellId(source: string, target: string): string {
  return `table-edge-${safeCellId(`${source}-${target}`)}`
}

export function fieldEdgeCellId(edge: LineageEdge): string {
  return `field-edge-${safeCellId(edgeKey(edge))}`
}

export function fieldPortId(direction: 'in' | 'out', field: string): string {
  return `${direction}:${field}`
}

function nodeHeight(table: LineageTableNode, expanded: boolean) {
  return expanded ? FIELD_TOP + table.fields.length * FIELD_ROW_HEIGHT + 14 : COLLAPSED_HEIGHT
}

function fieldPortY(index: number, expanded: boolean) {
  return expanded ? FIELD_TOP + index * FIELD_ROW_HEIGHT + FIELD_ROW_HEIGHT / 2 : HEADER_HEIGHT + 14
}

function connectedTableNames(payload: LineageGraphResponse) {
  const names = new Set([payload.root_table])
  payload.table_edges.forEach((edge) => {
    names.add(edge.source)
    names.add(edge.target)
  })
  return names
}

function tableLevel(payload: LineageGraphResponse, tableName: string, side: 'upstream' | 'downstream') {
  if (tableName === payload.root_table) return 0

  let frontier = new Set([payload.root_table])
  const seen = new Set(frontier)

  for (let depth = 1; depth <= payload.depth; depth += 1) {
    const next = new Set<string>()

    payload.table_edges.forEach((edge) => {
      if (side === 'upstream' && frontier.has(edge.target) && !seen.has(edge.source)) {
        next.add(edge.source)
      }
      if (side === 'downstream' && frontier.has(edge.source) && !seen.has(edge.target)) {
        next.add(edge.target)
      }
    })

    if (next.has(tableName)) return depth
    next.forEach((name) => seen.add(name))
    frontier = next
  }

  return 1
}

function buildPositions(payload: LineageGraphResponse) {
  const connected = connectedTableNames(payload)
  const upstream = payload.tables
    .filter((table) => table.name !== payload.root_table && connected.has(table.name))
    .filter((table) => payload.table_edges.some((edge) => edge.source === table.name && edge.direction === 'upstream'))
    .sort((a, b) => a.layer_priority - b.layer_priority || a.name.localeCompare(b.name))
  const downstream = payload.tables
    .filter((table) => table.name !== payload.root_table && connected.has(table.name))
    .filter((table) => payload.table_edges.some((edge) => edge.target === table.name && edge.direction === 'downstream'))
    .sort((a, b) => a.layer_priority - b.layer_priority || a.name.localeCompare(b.name))
  const positions = new Map<string, TablePosition>()

  positions.set(payload.root_table, { x: CENTER_X, y: CENTER_Y, side: 'root', level: 0 })

  upstream.forEach((table, index) => {
    const level = tableLevel(payload, table.name, 'upstream')
    positions.set(table.name, {
      x: CENTER_X - level * COLUMN_GAP,
      y: CENTER_Y + (index - (upstream.length - 1) / 2) * ROW_GAP,
      side: 'upstream',
      level,
    })
  })

  downstream.forEach((table, index) => {
    const level = tableLevel(payload, table.name, 'downstream')
    positions.set(table.name, {
      x: CENTER_X + level * COLUMN_GAP,
      y: CENTER_Y + (index - (downstream.length - 1) / 2) * ROW_GAP,
      side: 'downstream',
      level,
    })
  })

  return positions
}

function buildTableNode(
  table: LineageTableNode,
  position: TablePosition,
  rootTable: string,
  expanded: boolean,
): Node.Metadata {
  const palette = colorForLayer(table.layer)
  const height = nodeHeight(table, expanded)
  const markup = [
    { tagName: 'rect', selector: 'body' },
    { tagName: 'rect', selector: 'header' },
    { tagName: 'text', selector: 'title' },
    { tagName: 'text', selector: 'meta' },
    { tagName: 'rect', selector: 'toggleButton' },
    { tagName: 'text', selector: 'toggleLabel' },
  ]
  const attrs: NonNullable<Node.Metadata['attrs']> = {
    body: {
      width: NODE_WIDTH,
      height,
      rx: 8,
      ry: 8,
      fill: '#ffffff',
      stroke: table.name === rootTable ? '#2563eb' : palette.stroke,
      strokeWidth: table.name === rootTable ? 2 : 1,
      filter: table.name === rootTable ? 'drop-shadow(0 4px 12px rgba(37,99,235,0.18))' : undefined,
    },
    header: {
      width: NODE_WIDTH,
      height: HEADER_HEIGHT,
      rx: 8,
      ry: 8,
      fill: palette.fill,
      stroke: palette.stroke,
      strokeWidth: 1,
    },
    title: {
      x: 14,
      y: 22,
      text: table.name,
      fontSize: 13,
      fontWeight: 700,
      fill: '#172033',
    },
    meta: {
      x: 14,
      y: 40,
      text: `${table.layer} / ${table.storage_type} / ${table.field_count} fields`,
      fontSize: 10,
      fill: '#64748b',
    },
    toggleButton: {
      x: NODE_WIDTH - 34,
      y: 12,
      width: 22,
      height: 22,
      rx: 5,
      ry: 5,
      fill: '#ffffff',
      stroke: '#94a3b8',
      cursor: 'pointer',
      event: 'lineage:toggle-table',
    },
    toggleLabel: {
      x: NODE_WIDTH - 23,
      y: 28,
      text: expanded ? '-' : '+',
      textAnchor: 'middle',
      fontSize: 16,
      fontWeight: 700,
      fill: '#334155',
      cursor: 'pointer',
      event: 'lineage:toggle-table',
    },
  }

  if (expanded) {
    table.fields.forEach((field, index) => {
      const y = FIELD_TOP + index * FIELD_ROW_HEIGHT
      const rowSelector = `fieldRow${index}`
      const nameSelector = `fieldName${index}`
      const typeSelector = `fieldType${index}`

      markup.push({ tagName: 'rect', selector: rowSelector })
      markup.push({ tagName: 'text', selector: nameSelector })
      markup.push({ tagName: 'text', selector: typeSelector })
      attrs[rowSelector] = {
        x: 12,
        y,
        width: NODE_WIDTH - 24,
        height: FIELD_ROW_HEIGHT - 6,
        rx: 5,
        ry: 5,
        fill: '#f8fafc',
        stroke: '#e2e8f0',
      }
      attrs[nameSelector] = {
        x: 30,
        y: y + 15,
        text: field.name,
        fontSize: 11,
        fill: '#172033',
      }
      attrs[typeSelector] = {
        x: NODE_WIDTH - 82,
        y: y + 15,
        text: field.field_type,
        fontSize: 10,
        fill: '#64748b',
      }
    })
  }

  return {
    id: table.name,
    shape: 'lineage-table',
    x: position.x,
    y: position.y,
    width: NODE_WIDTH,
    height,
    markup,
    attrs,
    data: { kind: 'table', table, expanded, side: position.side, level: position.level },
    ports: {
      groups: {
        in: {
          position: { name: 'absolute' },
          attrs: { circle: { r: 5, magnet: true, stroke: '#2563eb', strokeWidth: 2, fill: '#ffffff' } },
        },
        out: {
          position: { name: 'absolute' },
          attrs: { circle: { r: 5, magnet: true, stroke: '#16a34a', strokeWidth: 2, fill: '#ffffff' } },
        },
      },
      items: table.fields.flatMap((field, index) => {
        const y = fieldPortY(index, expanded)
        return [
          { id: fieldPortId('in', field.name), group: 'in', args: { x: 0, y } },
          { id: fieldPortId('out', field.name), group: 'out', args: { x: NODE_WIDTH, y } },
        ]
      }),
    },
  }
}

function buildTableEdge(source: string, target: string): Edge.Metadata {
  return {
    id: tableEdgeCellId(source, target),
    shape: 'edge',
    source: { cell: source },
    target: { cell: target },
    connector: { name: 'smooth' },
    attrs: {
      line: {
        stroke: '#94a3b8',
        strokeWidth: 2,
        targetMarker: { name: 'block', width: 8, height: 6 },
      },
    },
    data: { kind: 'table-edge', source, target },
    zIndex: 1,
  }
}

function buildFieldEdge(edge: LineageEdge, selectedEdgeKey?: string): Edge.Metadata {
  const selected = selectedEdgeKey === edgeKey(edge)

  return {
    id: fieldEdgeCellId(edge),
    shape: 'edge',
    source: { cell: edge.from_table, port: fieldPortId('out', edge.from_field) },
    target: { cell: edge.to_table, port: fieldPortId('in', edge.to_field) },
    connector: { name: 'smooth' },
    attrs: {
      line: {
        stroke: selected ? '#2563eb' : '#64748b',
        strokeWidth: selected ? 3 : 2,
        strokeDasharray: '5 5',
        targetMarker: { name: 'block', width: 8, height: 6 },
      },
    },
    data: { kind: 'field-edge', edge },
    zIndex: selected ? 4 : 3,
  }
}

export function buildLineageX6GraphData({
  payload,
  expandedTables,
  selectedEdgeKey,
}: LineageX6GraphInput): LineageX6GraphData {
  if (!payload) return { nodes: [], edges: [], fieldEdgeByCellId: new Map() }

  const positions = buildPositions(payload)
  const nodes = payload.tables
    .filter((table) => positions.has(table.name))
    .map((table) =>
      buildTableNode(table, positions.get(table.name) ?? positions.get(payload.root_table)!, payload.root_table, expandedTables.has(table.name)),
    )
  const tableEdges = payload.table_edges.map((edge) => buildTableEdge(edge.source, edge.target))
  const fieldEdgeByCellId = new Map<string, LineageEdge>()
  const fieldEdges = payload.field_edges
    .filter((edge) => expandedTables.has(edge.from_table) || expandedTables.has(edge.to_table))
    .map((edge) => {
      const cellId = fieldEdgeCellId(edge)
      fieldEdgeByCellId.set(cellId, edge)
      return buildFieldEdge(edge, selectedEdgeKey)
    })

  return {
    nodes,
    edges: [...tableEdges, ...fieldEdges],
    fieldEdgeByCellId,
  }
}
