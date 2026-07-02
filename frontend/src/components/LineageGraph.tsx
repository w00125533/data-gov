import { Graph } from '@antv/g6'
import { Empty, List, Tag } from 'antd'
import { useEffect, useRef } from 'react'
import type { LineageEdge } from '../api/client'
import GraphToolbar from './GraphToolbar'
import { lineageToGraph } from './graphShared/graphData'

type Props = {
  edges: LineageEdge[]
  onSelectNode?: (nodeId: string) => void
  onSelectEdge?: (edge: LineageEdge) => void
  onContextMenu?: (payload: { x: number; y: number; targetType: 'node' | 'edge' | 'canvas'; targetId?: string }) => void
}

type GraphEvent = {
  target?: { id?: string }
  nativeEvent?: MouseEvent
}

type RuntimeGraph = {
  render: () => void
  destroy: () => void
  fitView?: () => void
  on?: (eventName: string, handler: (event: GraphEvent) => void) => void
}

function findEdge(edges: LineageEdge[], id?: string) {
  return edges.find((candidate) => {
    const fallbackId = `${candidate.from_table}.${candidate.from_field}->${candidate.to_table}.${candidate.to_field}`
    const legacyId = `${candidate.from_table}.${candidate.from_field}-${candidate.to_table}.${candidate.to_field}`
    return id === candidate.edge_id || id === fallbackId || id === legacyId
  })
}

function menuPayload(event: GraphEvent, targetType: 'node' | 'edge' | 'canvas') {
  const native = event.nativeEvent
  return {
    x: native?.clientX ?? 0,
    y: native?.clientY ?? 0,
    targetType,
    targetId: event.target?.id,
  }
}

export default function LineageGraph({ edges, onSelectNode, onSelectEdge, onContextMenu }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const graphRef = useRef<RuntimeGraph>()

  useEffect(() => {
    if (!ref.current || edges.length === 0) return
    const data = lineageToGraph(edges)
    const graph = new Graph({
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
    }) as RuntimeGraph
    graphRef.current = graph
    graph.render()
    graph.on?.('node:click', (event) => {
      const id = event.target?.id
      if (id) onSelectNode?.(id)
    })
    graph.on?.('edge:click', (event) => {
      const edge = findEdge(edges, event.target?.id)
      if (edge) onSelectEdge?.(edge)
    })
    graph.on?.('node:contextmenu', (event) => onContextMenu?.(menuPayload(event, 'node')))
    graph.on?.('edge:contextmenu', (event) => onContextMenu?.(menuPayload(event, 'edge')))
    graph.on?.('canvas:contextmenu', (event) => onContextMenu?.(menuPayload(event, 'canvas')))
    return () => {
      graph.destroy()
      graphRef.current = undefined
    }
  }, [edges, onContextMenu, onSelectEdge, onSelectNode])

  if (edges.length === 0) {
    return <Empty description="暂无血缘数据" />
  }

  return (
    <div className="graph-shell">
      <GraphToolbar
        onFit={() => graphRef.current?.fitView?.()}
        onFullscreen={() => ref.current?.requestFullscreen?.()}
      />
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
