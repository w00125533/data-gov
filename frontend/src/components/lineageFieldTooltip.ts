import type { LineageEdge } from '../api/client'

export function formatLineageFieldTooltip(edge: LineageEdge) {
  return edge.transform_expr?.trim() || '-'
}
