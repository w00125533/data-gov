import { Graph } from '@antv/g6'
import { Empty, List, Tag } from 'antd'
import { useEffect, useRef } from 'react'
import type { PipelineResponse } from '../api/client'
import GraphToolbar from './GraphToolbar'
import { pipelineToGraph } from './graphShared/graphData'
import { colorForLayer } from './graphShared/palette'

type Props = {
  payload?: PipelineResponse
  onSelectTable?: (table: string) => void
}

type GraphEvent = {
  target?: { id?: string }
}

type RuntimeGraph = {
  render: () => void
  destroy: () => void
  fitView?: () => void
  on?: (eventName: string, handler: (event: GraphEvent) => void) => void
}

export default function PipelineDAG({ payload, onSelectTable }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const graphRef = useRef<RuntimeGraph>()
  const data = pipelineToGraph(payload)

  useEffect(() => {
    if (!ref.current || data.nodes.length === 0) return
    const graph = new Graph({
      container: ref.current,
      autoFit: 'view',
      data,
      layout: { type: 'dagre', rankdir: payload?.mode === 'reverse' ? 'RL' : 'LR', nodesep: 42, ranksep: 100 },
      node: {
        type: 'rect',
        style: {
          size: [168, 42],
          radius: 6,
          labelFill: '#172033',
          labelFontWeight: 700,
          labelFontSize: 12,
        },
      },
      edge: {
        type: 'polyline',
        style: {
          endArrow: true,
          stroke: '#64748b',
          labelFill: '#475569',
          labelFontSize: 10,
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    }) as RuntimeGraph
    graphRef.current = graph
    graph.render()
    graph.on?.('node:click', (event) => {
      const id = event.target?.id
      if (id) onSelectTable?.(id)
    })
    return () => {
      graph.destroy()
      graphRef.current = undefined
    }
  }, [data, onSelectTable, payload?.mode])

  if (!payload || data.nodes.length === 0) {
    return <Empty description="暂无 Pipeline 数据" />
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
          dataSource={payload.nodes}
          renderItem={(node) => {
            const palette = colorForLayer(node.layer)
            return (
              <List.Item onClick={() => onSelectTable?.(node.name)}>
                <Tag color={palette.stroke}>{node.layer}</Tag>
                <strong>{node.name}</strong>
                <span className="muted">{node.field_count} fields</span>
              </List.Item>
            )
          }}
        />
      </div>
    </div>
  )
}
