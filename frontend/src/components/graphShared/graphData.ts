import type { LineageEdge, PipelineResponse } from '../../api/client'
import { colorForLayer } from './palette'

export type GraphDatum = {
  nodes: Array<{ id: string; data?: Record<string, unknown>; style?: Record<string, unknown> }>
  edges: Array<{ id?: string; source: string; target: string; data?: Record<string, unknown>; style?: Record<string, unknown> }>
}

export function lineageToGraph(edges: LineageEdge[]): GraphDatum {
  const nodes = new Map<string, { id: string; data: Record<string, unknown>; style: Record<string, unknown> }>()
  edges.forEach((edge) => {
    const from = `${edge.from_table}.${edge.from_field}`
    const to = `${edge.to_table}.${edge.to_field}`
    nodes.set(from, {
      id: from,
      data: { label: from, table: edge.from_table, field: edge.from_field },
      style: { labelText: from, fill: '#eff6ff', stroke: '#2563eb' },
    })
    nodes.set(to, {
      id: to,
      data: { label: to, table: edge.to_table, field: edge.to_field },
      style: { labelText: to, fill: '#f8fafc', stroke: '#64748b' },
    })
  })
  return {
    nodes: Array.from(nodes.values()),
    edges: edges.map((edge) => ({
      id: edge.edge_id || `${edge.from_table}.${edge.from_field}->${edge.to_table}.${edge.to_field}`,
      source: `${edge.from_table}.${edge.from_field}`,
      target: `${edge.to_table}.${edge.to_field}`,
      data: { ...edge },
      style: { labelText: edge.transform_expr || 'DERIVES_FROM' },
    })),
  }
}

export function pipelineToGraph(payload?: PipelineResponse): GraphDatum {
  if (!payload) return { nodes: [], edges: [] }
  return {
    nodes: payload.nodes.map((node) => {
      const palette = colorForLayer(node.layer)
      return {
        id: node.name,
        data: node,
        style: {
          labelText: node.name,
          fill: palette.fill,
          stroke: node.selected ? '#111827' : palette.stroke,
          lineWidth: node.selected ? 3 : 1.5,
        },
      }
    }),
    edges: payload.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      data: edge,
      style: { labelText: edge.constraint_summary || `${edge.weight} 字段` },
    })),
  }
}
