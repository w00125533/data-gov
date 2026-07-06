import { CommentOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Checkbox, Drawer, Input, Modal, Select, Slider, Space, Typography, message } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, type LineageEdge, type LineageGraphResponse, type LineageSqlImportPreviewResponse } from '../api/client'
import LineageContextMenu from '../components/LineageContextMenu'
import LineageEdgeEditor from '../components/LineageEdgeEditor'
import LineageSqlImportDrawer from '../components/LineageSqlImportDrawer'
import LineageSqlPanel from '../components/LineageSqlPanel'
import LineageWorkspaceGraph from '../components/LineageWorkspaceGraph'
import type { LineageMenuAction } from '../components/lineageContextMenuActions'
import { buildLineageTableSelectOptions, selectedLineageTableCard } from '../components/lineageTableSearch'

type EdgeModal = {
  mode: 'create' | 'edit'
  edge?: LineageEdge
  from?: string
  to?: string
  transform_expr?: string
}

type EdgeEndpoint = 'from' | 'to'

type ImportPreviewState = {
  preview: LineageSqlImportPreviewResponse
  graphVersion?: string
}

type ContextMenuState = {
  open: boolean
  x: number
  y: number
  targetType: 'node' | 'edge' | 'canvas'
  targetId?: string
}

function splitRef(value?: string) {
  const [table, field] = (value ?? '').split('.')
  return table && field ? { table, field } : undefined
}

function edgeId(edge: LineageEdge) {
  return edge.edge_id || `${edge.from_table}.${edge.from_field}->${edge.to_table}.${edge.to_field}`
}

function filterWorkspacePayload(payload: LineageGraphResponse | undefined, includeUpstream: boolean, includeDownstream: boolean) {
  if (!payload) return undefined
  const visibleNames = new Set([payload.root_table])
  let changed = true
  while (changed) {
    changed = false
    payload.table_edges.forEach((edge) => {
      if (includeUpstream && visibleNames.has(edge.target) && !visibleNames.has(edge.source)) {
        visibleNames.add(edge.source)
        changed = true
      }
      if (includeDownstream && visibleNames.has(edge.source) && !visibleNames.has(edge.target)) {
        visibleNames.add(edge.target)
        changed = true
      }
    })
  }

  return {
    ...payload,
    include_upstream: includeUpstream,
    include_downstream: includeDownstream,
    tables: payload.tables.filter((table) => visibleNames.has(table.name)),
    table_edges: payload.table_edges.filter((edge) => visibleNames.has(edge.source) && visibleNames.has(edge.target)),
    field_edges: payload.field_edges.filter((edge) => visibleNames.has(edge.from_table) && visibleNames.has(edge.to_table)),
  }
}

export default function Lineage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [apiMessage, holder] = message.useMessage()
  const [table, setTable] = useState(params.get('table') ?? 'dws_cell_hourly')
  const [depth, setDepth] = useState(Number(params.get('depth') ?? 5))
  const [includeUpstream, setIncludeUpstream] = useState(true)
  const [includeDownstream, setIncludeDownstream] = useState(true)
  const [expandedTables, setExpandedTables] = useState<Set<string>>(() => new Set())
  const [graphResetVersion, setGraphResetVersion] = useState(0)
  const [edge, setEdge] = useState<LineageEdge | undefined>()
  const [edgeEditorMode, setEdgeEditorMode] = useState<'edit' | 'create'>('edit')
  const [nodeId, setNodeId] = useState<string | undefined>()
  const [contextMenu, setContextMenu] = useState<ContextMenuState | undefined>()
  const [edgeModal, setEdgeModal] = useState<EdgeModal | undefined>()
  const [importOpen, setImportOpen] = useState(false)
  const [importPreviewState, setImportPreviewState] = useState<ImportPreviewState | undefined>()
  const importPreviewGeneration = useRef(0)

  const tablesQuery = useQuery({
    queryKey: ['tables', 'lineage-search'],
    queryFn: () => api.tables(),
  })

  const lineageQuery = useQuery({
    queryKey: ['lineage-graph', table, depth, includeUpstream, includeDownstream],
    queryFn: () => api.lineageGraph({
      table,
      depth,
      include_upstream: includeUpstream,
      include_downstream: includeDownstream,
    }),
  })

  const workspacePayload = filterWorkspacePayload(lineageQuery.data, includeUpstream, includeDownstream)
  const tableSelectOptions = useMemo(
    () => buildLineageTableSelectOptions(tablesQuery.data),
    [tablesQuery.data],
  )
  const selectedTableCard = useMemo(
    () => selectedLineageTableCard(tablesQuery.data, table) ?? { name: table, description: '当前根表' },
    [tablesQuery.data, table],
  )
  const invalidateLineage = () => queryClient.invalidateQueries({ queryKey: ['lineage-graph'] })

  const sqlPreviewQuery = useQuery({
    queryKey: ['lineage-sql-preview', table, lineageQuery.data?.graph_version],
    queryFn: () => api.previewLineageSql({ table }),
    enabled: Boolean(table),
  })

  const importPreviewMutation = useMutation({
    mutationFn: ({ sql }: { sql: string; generation: number; graphVersion?: string }) => api.previewLineageSqlImport({ table, sql }),
    onSuccess: (preview, variables) => {
      if (importOpen && variables.generation === importPreviewGeneration.current) {
        setImportPreviewState({ preview, graphVersion: variables.graphVersion })
      }
    },
    onError: (error, variables) => {
      if (importOpen && variables.generation === importPreviewGeneration.current) {
        apiMessage.error(`SQL 解析失败: ${(error as Error).message}`)
      }
    },
  })

  const importApplyMutation = useMutation({
    mutationFn: () => {
      if (!importPreviewState) throw new Error('missing import preview')
      return api.applyLineageSql({
        table,
        sql: importPreviewState.preview.sql,
        fields: importPreviewState.preview.fields,
        edges: importPreviewState.preview.edges,
        expected_graph_version: importPreviewState.graphVersion,
      })
    },
    onSuccess: () => {
      apiMessage.success('SQL 导入已应用')
      setImportOpen(false)
      setImportPreviewState(undefined)
      void invalidateLineage()
      void sqlPreviewQuery.refetch()
    },
    onError: (error) => apiMessage.error(`SQL 应用失败: ${(error as Error).message}`),
  })

  useEffect(() => {
    if (!edge) return
    if (edgeEditorMode === 'create') return
    const selectedEdgeId = edgeId(edge)
    const stillVisible = (workspacePayload?.field_edges ?? []).some((candidate) => edgeId(candidate) === selectedEdgeId)
    if (!stillVisible) {
      const handle = window.setTimeout(() => setEdge(undefined), 0)
      return () => window.clearTimeout(handle)
    }
  }, [edge, edgeEditorMode, workspacePayload])

  const createEdgeMutation = useMutation({
    mutationFn: api.createLineageEdge,
    onSuccess: () => {
      apiMessage.success('血缘边已创建')
      setEdge(undefined)
      setEdgeEditorMode('edit')
      setEdgeModal(undefined)
      void invalidateLineage()
      void sqlPreviewQuery.refetch()
    },
    onError: (error) => apiMessage.error(`创建失败: ${(error as Error).message}`),
  })
  const updateEdgeMutation = useMutation({
    mutationFn: (next: LineageEdge) => api.updateLineageEdge(edgeId(next), {
      transform_expr: next.transform_expr,
      calc_type: next.calc_type,
      calc_params: next.calc_params,
    }),
    onSuccess: (next) => {
      apiMessage.success('边配置已更新')
      setEdge(next)
      setEdgeEditorMode('edit')
      setEdgeModal(undefined)
      void invalidateLineage()
      void sqlPreviewQuery.refetch()
    },
    onError: (error) => apiMessage.error(`更新失败: ${(error as Error).message}`),
  })
  const moveEndpointMutation = useMutation({
    mutationFn: ({ id, nextEdge }: { id: string; nextEdge: LineageEdge }) =>
      api.updateLineageEdgeEndpoints(id, {
        from_table: nextEdge.from_table,
        from_field: nextEdge.from_field,
        to_table: nextEdge.to_table,
        to_field: nextEdge.to_field,
      }),
    onSuccess: (updated) => {
      apiMessage.success('端点已更新')
      setEdge(updated)
      void invalidateLineage()
      void sqlPreviewQuery.refetch()
    },
    onError: (error) => {
      apiMessage.error(`端点更新失败: ${(error as Error).message}`)
      setGraphResetVersion((version) => version + 1)
      void invalidateLineage()
      void sqlPreviewQuery.refetch()
    },
  })
  const deleteEdgeMutation = useMutation({
    mutationFn: api.deleteLineageEdge,
    onSuccess: () => {
      apiMessage.success('血缘边已删除')
      setEdge(undefined)
      void invalidateLineage()
      void sqlPreviewQuery.refetch()
    },
    onError: (error) => apiMessage.error(`删除失败: ${(error as Error).message}`),
  })

  function updateUrl(next: { table?: string; depth?: number }) {
    const search = new URLSearchParams(params)
    if (next.table) search.set('table', next.table)
    if (next.depth) search.set('depth', String(next.depth))
    setParams(search)
  }

  function selectRootTable(nextTable: string) {
    setTable(nextTable)
    setEdge(undefined)
    setEdgeEditorMode('edit')
    setNodeId(undefined)
    setExpandedTables(new Set())
    setContextMenu(undefined)
    updateUrl({ table: nextTable })
  }

  function closeImportDrawer() {
    importPreviewGeneration.current += 1
    setImportOpen(false)
    setImportPreviewState(undefined)
  }

  function openImportDrawer() {
    importPreviewGeneration.current += 1
    setImportPreviewState(undefined)
    setImportOpen(true)
  }

  function previewImportedSql(sql: string) {
    const generation = importPreviewGeneration.current + 1
    importPreviewGeneration.current = generation
    setImportPreviewState(undefined)
    importPreviewMutation.mutate({ sql, generation, graphVersion: lineageQuery.data?.graph_version })
  }

  function submitEdgeModal() {
    if (!edgeModal) return
    if (edgeModal.mode === 'edit' && edgeModal.edge) {
      updateEdgeMutation.mutate({ ...edgeModal.edge, transform_expr: edgeModal.transform_expr ?? '' })
      return
    }
    const from = splitRef(edgeModal.from)
    const to = splitRef(edgeModal.to)
    if (!from || !to) {
      apiMessage.warning('源字段和目标字段格式必须为 table.field')
      return
    }
    createEdgeMutation.mutate({
      from_table: from.table,
      from_field: from.field,
      to_table: to.table,
      to_field: to.field,
      transform_expr: edgeModal.transform_expr || 'passthrough',
    })
  }

  function chatHref() {
    const selectedField = edge?.to_field || nodeId?.split('.')[1]
    const selectedTable = edge?.to_table || nodeId?.split('.')[0] || table
    return `/chat?context=lineage&table=${selectedTable}${selectedField ? `&field=${selectedField}` : ''}`
  }

  function toggleTable(tableName: string) {
    setExpandedTables((prev) => {
      const next = new Set(prev)
      if (next.has(tableName)) {
        next.delete(tableName)
      } else {
        next.add(tableName)
      }
      return next
    })
  }

  function moveEndpoint(selectedEdge: LineageEdge, endpoint: EdgeEndpoint, nextTable: string, nextField: string) {
    const nextEdge = endpoint === 'from'
      ? { ...selectedEdge, from_table: nextTable, from_field: nextField }
      : { ...selectedEdge, to_table: nextTable, to_field: nextField }
    moveEndpointMutation.mutate({ id: edgeId(selectedEdge), nextEdge })
  }

  function createDraftFieldEdge(next: LineageEdge) {
    setEdge(next)
    setEdgeEditorMode('create')
    setNodeId(undefined)
  }

  function saveDrawerEdge(next: LineageEdge) {
    if (edgeEditorMode === 'create') {
      createEdgeMutation.mutate({
        from_table: next.from_table,
        from_field: next.from_field,
        to_table: next.to_table,
        to_field: next.to_field,
        transform_expr: next.transform_expr,
        calc_type: next.calc_type,
        calc_params: next.calc_params,
      })
      return
    }
    updateEdgeMutation.mutate(next)
  }

  function handleContextMenuAction(action: LineageMenuAction) {
    const targetTable = contextMenu?.targetType === 'node' ? contextMenu.targetId : undefined
    setContextMenu(undefined)

    if (action === 'create-downstream') {
      if (!targetTable) return
      navigate(`/metadata?table=${encodeURIComponent(targetTable)}&create_downstream=1`)
      return
    }

    if (action === 'create-edge') {
      setEdgeModal({ mode: 'create', transform_expr: 'passthrough' })
      return
    }

    if (action === 'chat') {
      navigate(chatHref())
      return
    }

    if (action === 'new-table') {
      navigate('/metadata?create_table=1')
      return
    }

    apiMessage.info('该右键操作将在后续版本完善')
  }

  return (
    <div className="lineage-page-grid">
      {holder}
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>血缘工作区</Typography.Title>
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Select
            showSearch
            value={table}
            placeholder="搜索并选择根表"
            style={{ width: '100%' }}
            options={tableSelectOptions.map((option) => ({
              value: option.value,
              label: option.label,
              searchText: option.searchText,
            }))}
            filterOption={(input, option) => String(option?.searchText ?? '').toLowerCase().includes(input.toLowerCase())}
            onChange={selectRootTable}
          />
          <div className="lineage-selected-table-card">
            <Typography.Text strong>{selectedTableCard.name}</Typography.Text>
            <Typography.Text className="muted">{selectedTableCard.description}</Typography.Text>
          </div>
          <Space className="lineage-depth-controls" wrap>
            <Typography.Text className="muted">展开层级: {depth}</Typography.Text>
            <Checkbox checked={includeDownstream} onChange={(event) => setIncludeDownstream(event.target.checked)}>前向</Checkbox>
            <Checkbox checked={includeUpstream} onChange={(event) => setIncludeUpstream(event.target.checked)}>后向</Checkbox>
          </Space>
          <Slider
            min={1}
            max={5}
            value={depth}
            onChange={(value) => {
              setDepth(value)
              updateUrl({ depth: value })
            }}
          />
          <LineageSqlPanel
            preview={sqlPreviewQuery.data}
            loading={sqlPreviewQuery.isFetching}
            onRefresh={() => { void sqlPreviewQuery.refetch() }}
            onSync={() => apiMessage.info('SQL 同步将在导入/应用流程中执行')}
            workflowActions={(
              <>
                <Button onClick={openImportDrawer}>导入 SQL</Button>
                <Button onClick={() => setEdgeModal({ mode: 'create', transform_expr: 'passthrough' })}>新建血缘边</Button>
                <Link to={chatHref()}>
                  <Button icon={<CommentOutlined />} type="primary">用 NL 修改</Button>
                </Link>
              </>
            )}
          />
        </Space>
      </section>
      <section className="panel panel-pad">
        <LineageWorkspaceGraph
          payload={workspacePayload}
          expandedTables={expandedTables}
          selectedEdge={edge}
          resetVersion={graphResetVersion}
          onToggleTable={toggleTable}
          onSelectFieldEdge={(next) => {
            setEdge(next)
            setEdgeEditorMode('edit')
            setNodeId(undefined)
          }}
          onCreateFieldEdge={createDraftFieldEdge}
          onMoveEdgeEndpoint={moveEndpoint}
          onContextMenu={(payload) => {
            setNodeId(payload.targetType === 'node' ? payload.targetId : undefined)
            setContextMenu({ open: true, ...payload })
          }}
        />
      </section>
      <Drawer
        title="字段级血缘边"
        open={Boolean(edge)}
        size={420}
        onClose={() => setEdge(undefined)}
        destroyOnHidden
      >
        <LineageEdgeEditor
          edge={edge}
          saving={updateEdgeMutation.isPending || createEdgeMutation.isPending}
          onSave={saveDrawerEdge}
          onDelete={() => {
            if (!edge) return
            if (edgeEditorMode === 'create') {
              setEdge(undefined)
              setEdgeEditorMode('edit')
              return
            }
            deleteEdgeMutation.mutate(edgeId(edge))
          }}
        />
      </Drawer>
      <Modal
        title={edgeModal?.mode === 'edit' ? '编辑血缘边' : '新建血缘边'}
        open={Boolean(edgeModal)}
        onCancel={() => setEdgeModal(undefined)}
        onOk={submitEdgeModal}
        confirmLoading={createEdgeMutation.isPending || updateEdgeMutation.isPending}
      >
        {edgeModal?.mode === 'create' ? (
          <Space orientation="vertical" style={{ width: '100%' }}>
            <Input value={edgeModal.from} placeholder="源字段: table.field" onChange={(event) => setEdgeModal({ ...edgeModal, from: event.target.value })} />
            <Input value={edgeModal.to} placeholder="目标字段: table.field" onChange={(event) => setEdgeModal({ ...edgeModal, to: event.target.value })} />
          </Space>
        ) : null}
        <Input.TextArea
          style={{ marginTop: 12 }}
          rows={4}
          value={edgeModal?.transform_expr}
          placeholder="转换表达式"
          onChange={(event) => edgeModal && setEdgeModal({ ...edgeModal, transform_expr: event.target.value })}
        />
      </Modal>
      <LineageSqlImportDrawer
        key={importOpen ? 'lineage-sql-import-open' : 'lineage-sql-import-closed'}
        open={importOpen}
        loading={importPreviewMutation.isPending || importApplyMutation.isPending}
        preview={importPreviewState?.preview}
        onClose={closeImportDrawer}
        onPreview={previewImportedSql}
        onApply={() => importApplyMutation.mutate()}
      />
      <LineageContextMenu
        open={Boolean(contextMenu?.open)}
        x={contextMenu?.x ?? 0}
        y={contextMenu?.y ?? 0}
        targetType={contextMenu?.targetType}
        onAction={handleContextMenuAction}
        onClose={() => setContextMenu(undefined)}
      />
    </div>
  )
}
