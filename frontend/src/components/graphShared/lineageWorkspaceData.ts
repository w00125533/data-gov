import type { LineageGraphResponse, LineageTableEdge, LineageTableNode } from '../../api/client'

export type WorkspaceTable = LineageTableNode & {
  expanded: boolean
  upstreamEdges: LineageTableEdge[]
  downstreamEdges: LineageTableEdge[]
}

export function buildWorkspaceTables(payload: LineageGraphResponse | undefined, expandedTables: Set<string>): WorkspaceTable[] {
  return (payload?.tables ?? []).map((table) => ({
    ...table,
    expanded: expandedTables.has(table.name),
    upstreamEdges: (payload?.table_edges ?? []).filter((edge) => edge.target === table.name),
    downstreamEdges: (payload?.table_edges ?? []).filter((edge) => edge.source === table.name),
  }))
}

export function edgeLabel(edge: LineageTableEdge) {
  const calcTypes = Object.entries(edge.calc_type_counts ?? {})
    .map(([type, count]) => `${type}: ${count}`)
    .join(', ')
  const fieldLabel = `${edge.field_edge_count} field edge${edge.field_edge_count === 1 ? '' : 's'}`
  return calcTypes ? `${fieldLabel} | ${calcTypes}` : fieldLabel
}
