import { Button, Empty, Space, Tag, Typography } from 'antd'
import type { DragEvent } from 'react'
import { useState } from 'react'
import type { LineageEdge, LineageGraphResponse } from '../api/client'
import { buildWorkspaceTables, edgeLabel } from './graphShared/lineageWorkspaceData'

type EdgeEndpoint = 'from' | 'to'

type Props = {
  payload?: LineageGraphResponse
  expandedTables: Set<string>
  onToggleTable: (table: string) => void
  onSelectFieldEdge: (edge: LineageEdge) => void
  onMoveEdgeEndpoint: (edge: LineageEdge, endpoint: EdgeEndpoint, table: string, field: string) => void
}

function edgeKey(edge: LineageEdge) {
  return edge.edge_id || `${edge.from_table}.${edge.from_field}->${edge.to_table}.${edge.to_field}`
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

export default function LineageWorkspaceGraph({
  payload,
  expandedTables,
  onToggleTable,
  onSelectFieldEdge,
  onMoveEdgeEndpoint,
}: Props) {
  const tables = buildWorkspaceTables(payload, expandedTables)
  const [pendingMove, setPendingMove] = useState<{ edgeKey: string; endpoint: EdgeEndpoint } | undefined>()

  function handleDragStart(event: DragEvent<HTMLElement>, edge: LineageEdge, endpoint: EdgeEndpoint) {
    event.dataTransfer.setData('application/lineage-edge-endpoint', dragPayload(edge, endpoint))
    event.dataTransfer.effectAllowed = 'move'
  }

  function handleDrop(event: DragEvent<HTMLElement>, table: string, field: string) {
    event.preventDefault()
    const raw = event.dataTransfer.getData('application/lineage-edge-endpoint')
    if (!raw) return
    const payloadData = parseDragPayload(raw)
    if (!payloadData) return
    const edge = findEdge(payload, payloadData.edgeKey)
    if (edge) onMoveEdgeEndpoint(edge, payloadData.endpoint, table, field)
  }

  function handleEndpointActivation(edge: LineageEdge, endpoint: EdgeEndpoint) {
    setPendingMove({ edgeKey: edgeKey(edge), endpoint })
  }

  function handleFieldActivation(table: string, field: string) {
    if (!pendingMove) return
    const edge = findEdge(payload, pendingMove.edgeKey)
    if (!edge) {
      setPendingMove(undefined)
      return
    }
    onMoveEdgeEndpoint(edge, pendingMove.endpoint, table, field)
    setPendingMove(undefined)
  }

  if (!payload || tables.length === 0) {
    return <Empty className="lineage-workspace-graph" description="暂无血缘工作区数据" />
  }

  return (
    <div className="lineage-workspace-graph">
      <div className="lineage-table-edge-layer" aria-label="表级血缘边">
        {(payload.table_edges ?? []).map((edge) => (
          <div className="lineage-table-edge" key={`${edge.source}->${edge.target}`}>
            <strong>{edge.source}</strong>
            <span>→</span>
            <strong>{edge.target}</strong>
            <span className="muted">{edgeLabel(edge)}</span>
          </div>
        ))}
      </div>

      <div className="lineage-table-grid">
        {tables.map((table) => (
          <article
            className={`lineage-table-node${table.name === payload.root_table ? ' selected' : ''}`}
            key={table.name}
          >
            <header>
              <Space orientation="vertical" size={2}>
                <Typography.Text strong>{table.name}</Typography.Text>
                <Typography.Text className="muted">
                  {table.layer} / {table.storage_type} / {table.field_count} fields
                </Typography.Text>
              </Space>
              <Button
                size="small"
                onClick={() => onToggleTable(table.name)}
                aria-label={`${table.expanded ? '折叠' : '展开'} ${table.name}`}
              >
                {table.expanded ? '折叠' : '展开'}
              </Button>
            </header>

            <div className="lineage-field-edge-list">
              {(payload.field_edges ?? [])
                .filter((edge) => edge.to_table === table.name)
                .map((edge) => (
                  <div
                    className="lineage-field-edge-row"
                    key={`${table.name}-${edgeKey(edge)}`}
                  >
                    <button
                      className="lineage-anchor"
                      draggable
                      type="button"
                      aria-label={`源锚点 ${edgeKey(edge)}`}
                      aria-pressed={pendingMove?.edgeKey === edgeKey(edge) && pendingMove.endpoint === 'from'}
                      onClick={() => handleEndpointActivation(edge, 'from')}
                      onDragStart={(event) => handleDragStart(event, edge, 'from')}
                    />
                    <button
                      className="lineage-field-edge-select"
                      type="button"
                      onClick={() => onSelectFieldEdge(edge)}
                    >
                      <span>{edge.from_table}.{edge.from_field}</span>
                      <span>→</span>
                      <span>{edge.to_table}.{edge.to_field}</span>
                      {edge.calc_type ? <Tag color="blue">{edge.calc_type}</Tag> : null}
                      <Typography.Text className="muted">{edge.transform_expr}</Typography.Text>
                    </button>
                    <button
                      className="lineage-anchor"
                      draggable
                      type="button"
                      aria-label={`目标锚点 ${edgeKey(edge)}`}
                      aria-pressed={pendingMove?.edgeKey === edgeKey(edge) && pendingMove.endpoint === 'to'}
                      onClick={() => handleEndpointActivation(edge, 'to')}
                      onDragStart={(event) => handleDragStart(event, edge, 'to')}
                    />
                  </div>
                ))}
            </div>

            {table.expanded ? (
              <div className="lineage-field-list">
                {table.fields.map((field) => (
                  <button
                    aria-label={`字段锚点 ${table.name}.${field.name}`}
                    className="lineage-field-row"
                    key={field.id || `${table.name}.${field.name}`}
                    type="button"
                    onClick={() => handleFieldActivation(table.name, field.name)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => handleDrop(event, table.name, field.name)}
                  >
                    <span className="lineage-anchor" />
                    <Typography.Text>{field.name}</Typography.Text>
                    <Typography.Text className="muted">{field.field_type}</Typography.Text>
                    {field.expression ? <Typography.Text className="muted">{field.expression}</Typography.Text> : null}
                  </button>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  )
}
