import { CommentOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Input, Modal, Segmented, Slider, Space, Typography, message } from 'antd'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, type LineageEdge } from '../api/client'
import LineageContextMenu, { type LineageMenuAction } from '../components/LineageContextMenu'
import LineageGraph from '../components/LineageGraph'
import LineageSidePanel from '../components/LineageSidePanel'

type EdgeModal = {
  mode: 'create' | 'edit'
  edge?: LineageEdge
  from?: string
  to?: string
  transform_expr?: string
}

function splitRef(value?: string) {
  const [table, field] = (value ?? '').split('.')
  return table && field ? { table, field } : undefined
}

function edgeId(edge: LineageEdge) {
  return edge.edge_id || `${edge.from_table}.${edge.from_field}->${edge.to_table}.${edge.to_field}`
}

export default function Lineage() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [apiMessage, holder] = message.useMessage()
  const [table, setTable] = useState(params.get('table') ?? 'dws_cell_hourly')
  const [direction, setDirection] = useState<'up' | 'down'>((params.get('direction') as 'up' | 'down') ?? 'down')
  const [depth, setDepth] = useState(Number(params.get('depth') ?? 5))
  const [edge, setEdge] = useState<LineageEdge | undefined>()
  const [nodeId, setNodeId] = useState<string | undefined>()
  const [edgeModal, setEdgeModal] = useState<EdgeModal | undefined>()
  const [menu, setMenu] = useState<{ open: boolean; x: number; y: number; targetType: 'node' | 'edge' | 'canvas'; targetId?: string }>({
    open: false,
    x: 0,
    y: 0,
    targetType: 'canvas',
  })

  const lineageQuery = useQuery({
    queryKey: ['lineage', table, direction, depth],
    queryFn: () => api.lineage({ table, direction, depth }),
  })

  const invalidateLineage = () => queryClient.invalidateQueries({ queryKey: ['lineage'] })
  const createEdgeMutation = useMutation({
    mutationFn: api.createLineageEdge,
    onSuccess: () => {
      apiMessage.success('血缘边已创建')
      setEdgeModal(undefined)
      invalidateLineage()
    },
    onError: (error) => apiMessage.error(`创建失败: ${(error as Error).message}`),
  })
  const updateEdgeMutation = useMutation({
    mutationFn: ({ id, transform_expr }: { id: string; transform_expr: string }) => api.updateLineageEdge(id, { transform_expr }),
    onSuccess: (next) => {
      apiMessage.success('表达式已更新')
      setEdge(next)
      setEdgeModal(undefined)
      invalidateLineage()
    },
    onError: (error) => apiMessage.error(`更新失败: ${(error as Error).message}`),
  })
  const deleteEdgeMutation = useMutation({
    mutationFn: api.deleteLineageEdge,
    onSuccess: () => {
      apiMessage.success('血缘边已删除')
      setEdge(undefined)
      invalidateLineage()
    },
    onError: (error) => apiMessage.error(`删除失败: ${(error as Error).message}`),
  })

  function updateUrl(next: { table?: string; direction?: 'up' | 'down'; depth?: number }) {
    const search = new URLSearchParams(params)
    if (next.table) search.set('table', next.table)
    if (next.direction) search.set('direction', next.direction)
    if (next.depth) search.set('depth', String(next.depth))
    setParams(search)
  }

  function submitEdgeModal() {
    if (!edgeModal) return
    if (edgeModal.mode === 'edit' && edgeModal.edge) {
      updateEdgeMutation.mutate({ id: edgeId(edgeModal.edge), transform_expr: edgeModal.transform_expr ?? '' })
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

  function handleMenuAction(action: LineageMenuAction) {
    setMenu((prev) => ({ ...prev, open: false }))
    if (action === 'edit-edge' && edge) {
      setEdgeModal({ mode: 'edit', edge, transform_expr: edge.transform_expr })
    }
    if (action === 'delete-edge' && edge) {
      deleteEdgeMutation.mutate(edgeId(edge))
    }
    if (action === 'create-edge') {
      setEdgeModal({ mode: 'create', from: nodeId, transform_expr: 'passthrough' })
    }
    if (action === 'chat') {
      window.location.href = chatHref()
    }
  }

  return (
    <div className="three-panel-grid">
      {holder}
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>字段级血缘</Typography.Title>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input.Search
            value={table}
            onChange={(event) => setTable(event.target.value)}
            onSearch={(value) => {
              updateUrl({ table: value })
            }}
          />
          <Segmented
            value={direction}
            options={[{ label: '正向', value: 'down' }, { label: '反向', value: 'up' }]}
            onChange={(value) => {
              setDirection(value as 'up' | 'down')
              updateUrl({ direction: value as 'up' | 'down' })
            }}
          />
          <Typography.Text className="muted">展开层级: {depth}</Typography.Text>
          <Slider
            min={1}
            max={5}
            value={depth}
            onChange={(value) => {
              setDepth(value)
              updateUrl({ depth: value })
            }}
          />
          <Button onClick={() => setEdgeModal({ mode: 'create', transform_expr: 'passthrough' })}>新建血缘边</Button>
          <Link to={chatHref()}>
            <Button icon={<CommentOutlined />} type="primary">用 NL 修改</Button>
          </Link>
        </Space>
      </section>
      <section className="panel panel-pad">
        <LineageGraph
          edges={lineageQuery.data?.edges ?? []}
          onSelectNode={(id) => {
            setNodeId(id)
            setEdge(undefined)
          }}
          onSelectEdge={(next) => {
            setEdge(next)
            setNodeId(undefined)
          }}
          onContextMenu={(payload) => setMenu({ open: true, ...payload })}
        />
        <LineageContextMenu
          open={menu.open}
          x={menu.x}
          y={menu.y}
          targetType={menu.targetType}
          onClose={() => setMenu((prev) => ({ ...prev, open: false }))}
          onAction={handleMenuAction}
        />
      </section>
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>详情</Typography.Title>
        <LineageSidePanel
          edge={edge}
          nodeId={nodeId}
          onEditEdge={() => edge && setEdgeModal({ mode: 'edit', edge, transform_expr: edge.transform_expr })}
          onDeleteEdge={() => edge && deleteEdgeMutation.mutate(edgeId(edge))}
          onChat={() => { window.location.href = chatHref() }}
        />
      </section>
      <Modal
        title={edgeModal?.mode === 'edit' ? '编辑血缘边' : '新建血缘边'}
        open={Boolean(edgeModal)}
        onCancel={() => setEdgeModal(undefined)}
        onOk={submitEdgeModal}
        confirmLoading={createEdgeMutation.isPending || updateEdgeMutation.isPending}
      >
        {edgeModal?.mode === 'create' ? (
          <Space direction="vertical" style={{ width: '100%' }}>
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
    </div>
  )
}
