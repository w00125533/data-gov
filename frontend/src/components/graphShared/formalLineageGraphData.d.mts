import type {
  FormalFieldLineageEdge,
  FormalLineageEdge,
  FormalLineageResponse,
} from '../../api/client'

export type FormalLineageGraphEdgeData =
  | { edgeKind: 'field'; rawEdge: FormalFieldLineageEdge }
  | { edgeKind: 'asset'; rawEdge: FormalLineageEdge }

export type FormalLineageGraphDatum = {
  nodes: Array<{ id: string; data?: Record<string, unknown>; style?: Record<string, unknown> }>
  edges: Array<{
    id: string
    source: string
    target: string
    data: FormalLineageGraphEdgeData
    style: Record<string, unknown>
  }>
}

export function formalLineageToGraph(lineage?: Pick<FormalLineageResponse, 'nodes' | 'edges' | 'fieldEdges'>): FormalLineageGraphDatum
