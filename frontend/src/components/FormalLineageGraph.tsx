import { Graph } from '@antv/g6'
import { Empty, List, Tag } from 'antd'
import { useEffect, useMemo, useRef } from 'react'
import type {
  FormalFieldLineageEdge,
  FormalLineageEdge,
  FormalLineageResponse,
} from '../api/client'
import { formalLineageToGraph, type FormalLineageGraphEdgeData } from './graphShared/formalLineageGraphData.mjs'

type Props = {
  lineage?: FormalLineageResponse
  onSelectEdge?: (edge: FormalFieldLineageEdge | FormalLineageEdge, edgeKind: FormalLineageGraphEdgeData['edgeKind']) => void
}

type GraphEvent = {
  target?: {
    id?: string
  }
}

function graphTargetId(event: unknown) {
  return (event as GraphEvent).target?.id
}

export default function FormalLineageGraph({ lineage, onSelectEdge }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const graphData = useMemo(() => formalLineageToGraph(lineage), [lineage])

  useEffect(() => {
    if (!ref.current || graphData.edges.length === 0) return
    const graph = new Graph({
      container: ref.current,
      autoFit: 'view',
      data: graphData,
      layout: { type: 'dagre', rankdir: 'LR', nodesep: 36, ranksep: 90 },
      node: {
        type: 'rect',
        style: {
          size: [210, 38],
          radius: 6,
          labelFill: '#172033',
          labelFontSize: 11,
        },
      },
      edge: {
        type: 'polyline',
        style: {
          endArrow: true,
          stroke: '#94a3b8',
          labelFill: '#64748b',
          labelFontSize: 10,
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    })
    graph.render()
    graph.on?.('edge:click', (event: unknown) => {
      const id = graphTargetId(event)
      const edge = graphData.edges.find((candidate) => candidate.id === id)
      if (edge) onSelectEdge?.(edge.data.rawEdge, edge.data.edgeKind)
    })
    return () => graph.destroy()
  }, [graphData, onSelectEdge])

  if (graphData.edges.length === 0) {
    return <Empty description="暂无正式血缘数据" />
  }

  return (
    <div className="graph-shell">
      <div className="graph-container" ref={ref} />
      <div className="graph-fallback">
        <List
          size="small"
          dataSource={graphData.edges.slice(0, 8)}
          renderItem={(edge) => (
            <List.Item onClick={() => onSelectEdge?.(edge.data.rawEdge, edge.data.edgeKind)}>
              <Tag color={edge.data.edgeKind === 'field' ? 'blue' : 'green'}>{edge.source}</Tag>
              <span className="muted">→</span>
              <Tag>{edge.target}</Tag>
            </List.Item>
          )}
        />
      </div>
    </div>
  )
}
