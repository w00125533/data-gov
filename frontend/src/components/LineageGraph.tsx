import { Graph } from '@antv/g6'
import { Empty, List, Tag } from 'antd'
import { useEffect, useRef } from 'react'
import type { LineageEdge } from '../api/client'
import { lineageToGraph } from './graphShared/graphData'

type Props = {
  edges: LineageEdge[]
  onSelectEdge?: (edge: LineageEdge) => void
}

export default function LineageGraph({ edges, onSelectEdge }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || edges.length === 0) return
    const data = lineageToGraph(edges)
    const graph: any = new Graph({
      container: ref.current,
      autoFit: 'view',
      data,
      layout: { type: 'dagre', rankdir: 'LR', nodesep: 36, ranksep: 90 },
      node: {
        type: 'rect',
        style: {
          size: [180, 36],
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
    graph.on?.('edge:click', (event: any) => {
      const id = event.target?.id as string | undefined
      const edge = edges.find((candidate) => `${candidate.from_table}.${candidate.from_field}-${candidate.to_table}.${candidate.to_field}` === id)
      if (edge) onSelectEdge?.(edge)
    })
    return () => graph.destroy()
  }, [edges, onSelectEdge])

  if (edges.length === 0) {
    return <Empty description="暂无血缘数据" />
  }

  return (
    <div className="graph-shell">
      <div className="graph-container" ref={ref} />
      <div className="graph-fallback">
        <List
          size="small"
          dataSource={edges.slice(0, 8)}
          renderItem={(edge) => (
            <List.Item onClick={() => onSelectEdge?.(edge)}>
              <Tag color="blue">{edge.from_table}.{edge.from_field}</Tag>
              <span className="muted">→</span>
              <Tag>{edge.to_table}.{edge.to_field}</Tag>
            </List.Item>
          )}
        />
      </div>
    </div>
  )
}
