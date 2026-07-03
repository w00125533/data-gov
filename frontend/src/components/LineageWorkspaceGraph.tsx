import { Empty, Tooltip, Typography } from 'antd'
import { Graph } from '@antv/x6'
import type { Edge } from '@antv/x6'
import { MiniMap } from '@antv/x6-plugin-minimap'
import '@antv/x6/dist/index.css'
import type { DragEvent } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { LineageEdge, LineageGraphResponse } from '../api/client'
import { buildLineageX6GraphData, edgeKey } from './graphShared/lineageX6Adapter'

type EdgeEndpoint = 'from' | 'to'

type Props = {
  payload?: LineageGraphResponse
  expandedTables: Set<string>
  selectedEdge?: LineageEdge
  onToggleTable: (table: string) => void
  onSelectFieldEdge: (edge: LineageEdge) => void
  onMoveEdgeEndpoint: (edge: LineageEdge, endpoint: EdgeEndpoint, table: string, field: string) => void
}

type PendingMove = {
  edgeKey: string
  endpoint: EdgeEndpoint
}

type TooltipState = {
  edge: LineageEdge
  left: number
  top: number
}

type FieldEdgeData = {
  kind?: string
  edge?: LineageEdge
}

function findEdge(payload: LineageGraphResponse | undefined, key: string) {
  return (payload?.field_edges ?? []).find((edge) => edgeKey(edge) === key)
}

function dragPayload(edge: LineageEdge, endpoint: EdgeEndpoint) {
  return JSON.stringify({ edgeKey: edgeKey(edge), endpoint })
}

function parseDragPayload(raw: string) {
  try {
    const parsed = JSON.parse(raw) as { edgeKey?: unknown; endpoint?: unknown }
    if (typeof parsed.edgeKey !== 'string') return undefined
    if (parsed.endpoint !== 'from' && parsed.endpoint !== 'to') return undefined
    return { edgeKey: parsed.edgeKey, endpoint: parsed.endpoint as EdgeEndpoint }
  } catch {
    return undefined
  }
}

function terminalParts(edge: Edge, endpoint: EdgeEndpoint) {
  const terminal = endpoint === 'from' ? edge.getSource() : edge.getTarget()
  const cell = 'cell' in terminal && typeof terminal.cell === 'string' ? terminal.cell : undefined
  const port = 'port' in terminal && typeof terminal.port === 'string' ? terminal.port : undefined
  const field = port?.split(':').slice(1).join(':')

  if (!cell || !field) return undefined
  return { table: cell, field }
}

function renderTooltipContent(edge: LineageEdge) {
  return (
    <div className="lineage-x6-tooltip-content">
      <Typography.Text strong>{edge.from_table}.{edge.from_field}</Typography.Text>
      <Typography.Text strong>{edge.to_table}.{edge.to_field}</Typography.Text>
      <Typography.Text>{edge.calc_type ?? 'UNKNOWN'}</Typography.Text>
      <Typography.Text>{edge.transform_expr || '-'}</Typography.Text>
    </div>
  )
}

export default function LineageWorkspaceGraph({
  payload,
  expandedTables,
  selectedEdge,
  onToggleTable,
  onSelectFieldEdge,
  onMoveEdgeEndpoint,
}: Props) {
  const canvasRef = useRef<HTMLDivElement | null>(null)
  const minimapRef = useRef<HTMLDivElement | null>(null)
  const graphRef = useRef<Graph | null>(null)
  const callbacksRef = useRef({ onToggleTable, onSelectFieldEdge, onMoveEdgeEndpoint })
  const payloadRef = useRef(payload)
  const [pendingMove, setPendingMove] = useState<PendingMove | undefined>()
  const [tooltip, setTooltip] = useState<TooltipState | undefined>()
  const [containersReady, setContainersReady] = useState(false)
  const [graphReady, setGraphReady] = useState(false)
  const graphData = useMemo(
    () => buildLineageX6GraphData({
      payload,
      expandedTables,
    }),
    [payload, expandedTables],
  )
  const selectedEdgeKey = selectedEdge ? edgeKey(selectedEdge) : undefined
  const topologyKey = useMemo(() => {
    const tables = (payload?.tables ?? []).map((table) => table.name).sort().join('|')
    const expanded = Array.from(expandedTables).sort().join('|')
    return `${payload?.graph_version ?? 'empty'}:${tables}:${expanded}`
  }, [payload, expandedTables])

  useEffect(() => {
    callbacksRef.current = { onToggleTable, onSelectFieldEdge, onMoveEdgeEndpoint }
  }, [onToggleTable, onSelectFieldEdge, onMoveEdgeEndpoint])

  useEffect(() => {
    payloadRef.current = payload
  }, [payload])

  const markContainersReady = useCallback(() => {
    if (canvasRef.current && minimapRef.current) {
      setContainersReady(true)
    }
  }, [])

  const setCanvasRef = useCallback((element: HTMLDivElement | null) => {
    canvasRef.current = element
    if (element) markContainersReady()
  }, [markContainersReady])

  const setMinimapRef = useCallback((element: HTMLDivElement | null) => {
    minimapRef.current = element
    if (element) markContainersReady()
  }, [markContainersReady])

  useEffect(() => {
    if (!containersReady || !canvasRef.current || !minimapRef.current || graphRef.current) return

    const graph = new Graph({
      container: canvasRef.current,
      autoResize: true,
      background: { color: '#f8fafc' },
      grid: {
        visible: true,
        type: 'mesh',
        args: {
          color: '#dbe3ef',
          thickness: 1,
        },
      },
      panning: {
        enabled: true,
        eventTypes: ['leftMouseDown', 'rightMouseDown'],
      },
      mousewheel: {
        enabled: true,
        modifiers: ['ctrl', 'meta'],
        minScale: 0.4,
        maxScale: 1.8,
      },
      connecting: {
        snap: true,
        allowBlank: false,
        allowLoop: false,
        allowNode: false,
        allowEdge: false,
        allowPort: true,
        allowMulti: 'withPort',
        highlight: true,
        connector: 'smooth',
        validateConnection({ sourceCell, targetCell, sourcePort, targetPort }) {
          return Boolean(sourceCell && targetCell && sourcePort?.startsWith('out:') && targetPort?.startsWith('in:'))
        },
      },
      interacting: {
        nodeMovable: false,
        edgeMovable: false,
        vertexMovable: false,
        arrowheadMovable: true,
      },
    })

    graph.use(new MiniMap({
      container: minimapRef.current,
      width: 150,
      height: 96,
      padding: 8,
      scalable: true,
    }))

    graph.on('cell:customevent', ({ name, cell }) => {
      if (name === 'lineage:toggle-table') {
        callbacksRef.current.onToggleTable(cell.id)
      }
    })

    graph.on('edge:click', ({ edge }) => {
      const data = edge.getData<FieldEdgeData>()
      if (data?.kind === 'field-edge' && data.edge) {
        callbacksRef.current.onSelectFieldEdge(data.edge)
      }
    })

    graph.on('edge:mouseenter', ({ edge, e }) => {
      const data = edge.getData<FieldEdgeData>()
      if (data?.kind === 'field-edge' && data.edge) {
        setTooltip({ edge: data.edge, left: e.clientX, top: e.clientY })
      }
    })

    graph.on('edge:mousemove', ({ edge, e }) => {
      const data = edge.getData<FieldEdgeData>()
      if (data?.kind === 'field-edge' && data.edge) {
        setTooltip({ edge: data.edge, left: e.clientX, top: e.clientY })
      }
    })

    graph.on('edge:mouseleave', () => setTooltip(undefined))

    graph.on('edge:connected', ({ edge, isNew, type }) => {
      if (isNew) {
        edge.remove()
        return
      }

      const data = edge.getData<FieldEdgeData>()
      if (data?.kind !== 'field-edge' || !data.edge) return

      const endpoint = type === 'source' ? 'from' : 'to'
      const next = terminalParts(edge, endpoint)
      if (!next) return
      callbacksRef.current.onMoveEdgeEndpoint(data.edge, endpoint, next.table, next.field)
    })

    graphRef.current = graph
    setGraphReady(true)

    return () => {
      graph.dispose()
      graphRef.current = null
      setGraphReady(false)
    }
  }, [containersReady])

  useEffect(() => {
    const graph = graphRef.current
    if (!graphReady || !graph) return

    const cells = graph.parseJSON({ cells: [...graphData.nodes, ...graphData.edges] } as Parameters<Graph['parseJSON']>[0])
    graph.resetCells(cells)
    if (graphData.nodes.length > 0) {
      const frame = window.requestAnimationFrame(() => {
        if (graphRef.current === graph) {
          graph.centerContent()
        }
      })
      return () => window.cancelAnimationFrame(frame)
    }
  }, [graphData, graphReady, topologyKey])

  useEffect(() => {
    const graph = graphRef.current
    if (!graphReady || !graph) return

    graph.getEdges().forEach((edge) => {
      const data = edge.getData<FieldEdgeData & { lineageEdgeKey?: string }>()
      if (data?.kind !== 'field-edge') return

      const selected = data.lineageEdgeKey === selectedEdgeKey
      edge.attr('line/stroke', selected ? '#2563eb' : '#64748b')
      edge.attr('line/strokeWidth', selected ? 3 : 2)
      edge.attr('line/opacity', selectedEdgeKey ? (selected ? 1 : 0.45) : 1)
      edge.setZIndex(selected ? 4 : 3)
    })
  }, [selectedEdgeKey, graphData, graphReady])

  function handleDragStart(event: DragEvent<HTMLButtonElement>, edge: LineageEdge, endpoint: EdgeEndpoint) {
    event.dataTransfer.setData('application/lineage-edge-endpoint', dragPayload(edge, endpoint))
    event.dataTransfer.effectAllowed = 'move'
  }

  function handleDrop(event: DragEvent<HTMLButtonElement>, table: string, field: string) {
    event.preventDefault()
    const payloadData = parseDragPayload(event.dataTransfer.getData('application/lineage-edge-endpoint'))
    if (!payloadData) return

    const edge = findEdge(payloadRef.current, payloadData.edgeKey)
    if (edge) callbacksRef.current.onMoveEdgeEndpoint(edge, payloadData.endpoint, table, field)
  }

  function handleEndpointActivation(edge: LineageEdge, endpoint: EdgeEndpoint) {
    setPendingMove({ edgeKey: edgeKey(edge), endpoint })
  }

  function handleFieldActivation(table: string, field: string) {
    if (!pendingMove) return

    const edge = findEdge(payloadRef.current, pendingMove.edgeKey)
    if (edge) callbacksRef.current.onMoveEdgeEndpoint(edge, pendingMove.endpoint, table, field)
    setPendingMove(undefined)
  }

  const isEmpty = !payload || graphData.nodes.length === 0

  return (
    <div className="lineage-workspace-graph lineage-x6-shell">
      <div className="lineage-x6-canvas">
        <div className="lineage-x6-graph-host" ref={setCanvasRef} />
      </div>
      <div className="lineage-x6-minimap" ref={setMinimapRef} />
      <Tooltip open={Boolean(tooltip)} title={tooltip ? renderTooltipContent(tooltip.edge) : null}>
        <span
          className="lineage-x6-tooltip-anchor"
          style={{ left: tooltip?.left ?? -9999, top: tooltip?.top ?? -9999 }}
        />
      </Tooltip>
      {isEmpty ? (
        <Empty className="lineage-x6-empty" description="鏆傛棤琛€缂樺伐浣滃尯鏁版嵁" />
      ) : null}
      {payload ? (
        <div className="lineage-x6-accessible" aria-label="lineage graph controls">
          {payload.tables.map((table) => {
          const expanded = expandedTables.has(table.name)
          return (
            <button
              aria-label={`${expanded ? '折叠' : '展开'} ${table.name}`}
              key={table.name}
              type="button"
              onClick={() => onToggleTable(table.name)}
            >
              {expanded ? 'collapse' : 'expand'} table {table.name}
            </button>
          )
          })}
          {(payload.field_edges ?? []).map((edge) => {
          const key = edgeKey(edge)
          return (
            <span key={key}>
              <button type="button" onClick={() => onSelectFieldEdge(edge)}>
                field edge {key} {edge.from_table}.{edge.from_field} {edge.to_table}.{edge.to_field}
              </button>
              <button
                aria-label={`源锚点 ${key}`}
                aria-pressed={pendingMove?.edgeKey === key && pendingMove.endpoint === 'from'}
                draggable
                type="button"
                onClick={() => handleEndpointActivation(edge, 'from')}
                onDragStart={(event) => handleDragStart(event, edge, 'from')}
              >
                source endpoint {key}
              </button>
              <button
                aria-label={`目标锚点 ${key}`}
                aria-pressed={pendingMove?.edgeKey === key && pendingMove.endpoint === 'to'}
                draggable
                type="button"
                onClick={() => handleEndpointActivation(edge, 'to')}
                onDragStart={(event) => handleDragStart(event, edge, 'to')}
              >
                target endpoint {key}
              </button>
            </span>
          )
          })}
          {payload.tables.flatMap((table) =>
          table.fields.map((field) => (
            <button
              aria-label={`字段锚点 ${table.name}.${field.name}`}
              key={`${table.name}.${field.name}`}
              type="button"
              onClick={() => handleFieldActivation(table.name, field.name)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => handleDrop(event, table.name, field.name)}
            >
              field port {table.name}.{field.name}
            </button>
          )),
          )}
        </div>
      ) : null}
    </div>
  )
}
