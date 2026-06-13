import { CommentOutlined, ReloadOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Descriptions,
  Divider,
  Input,
  Segmented,
  Slider,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from 'antd'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  api,
  type FormalFieldLineageEdge,
  type FormalLineageEdge,
  type FormalMetadataSummary,
  type LineageEdge,
} from '../api/client'
import FormalLineageGraph from '../components/FormalLineageGraph'
import LineageGraph from '../components/LineageGraph'

type LineageSource = 'formal' | 'legacy'
type SelectedFormalEdge = {
  edge: FormalFieldLineageEdge | FormalLineageEdge
  edgeKind: 'field' | 'asset'
}

function sourceFromParams(value: string | null): LineageSource {
  return value === 'legacy' ? 'legacy' : 'formal'
}

function directionFromParams(value: string | null): 'up' | 'down' {
  return value === 'up' ? 'up' : 'down'
}

function formalEdgeEndpoint(edge: FormalFieldLineageEdge | FormalLineageEdge, edgeKind: 'field' | 'asset', side: 'source' | 'target') {
  if (edgeKind === 'field') {
    const fieldEdge = edge as FormalFieldLineageEdge
    return side === 'source'
      ? `${fieldEdge.sourceAssetCode}.${fieldEdge.sourceField}`
      : `${fieldEdge.targetAssetCode}.${fieldEdge.targetField}`
  }
  return side === 'source' ? edge.sourceAssetCode : edge.targetAssetCode
}

export default function Lineage() {
  const [params, setParams] = useSearchParams()
  const [source, setSource] = useState<LineageSource>(sourceFromParams(params.get('source')))
  const [table, setTable] = useState(params.get('table') ?? 'dws_cell_hourly')
  const [formalKeyword, setFormalKeyword] = useState(params.get('asset') ?? '')
  const [selectedMetadataId, setSelectedMetadataId] = useState(params.get('metadataId') ?? '')
  const [direction, setDirection] = useState<'up' | 'down'>(directionFromParams(params.get('direction')))
  const [depth, setDepth] = useState(Number(params.get('depth') ?? 5))
  const [legacyEdge, setLegacyEdge] = useState<LineageEdge | undefined>()
  const [formalEdge, setFormalEdge] = useState<SelectedFormalEdge | undefined>()

  const lineageQuery = useQuery({
    queryKey: ['lineage', table, direction, depth],
    queryFn: () => api.lineage({ table, direction, depth }),
    enabled: source === 'legacy',
  })

  const formalMetadataQuery = useQuery({
    queryKey: ['formal-metadata', formalKeyword],
    queryFn: () => api.formalMetadata({ keyword: formalKeyword, page: 1, size: 20 }),
    enabled: source === 'formal',
  })

  const selectedMetadata = useMemo<FormalMetadataSummary | undefined>(() => {
    return formalMetadataQuery.data?.items.find((item) => item.metadataId === selectedMetadataId)
      ?? formalMetadataQuery.data?.items[0]
  }, [formalMetadataQuery.data?.items, selectedMetadataId])

  const formalLineageQuery = useQuery({
    queryKey: ['formal-lineage', selectedMetadata?.metadataId, direction, depth],
    queryFn: () => api.formalLineage({ metadataId: selectedMetadata!.metadataId, direction, depth }),
    enabled: source === 'formal' && Boolean(selectedMetadata?.metadataId),
  })

  function updateParam(key: string, value?: string | number) {
    const next = new URLSearchParams(params)
    if (value === undefined || value === '') next.delete(key)
    else next.set(key, String(value))
    setParams(next)
  }

  function selectSource(value: LineageSource) {
    setSource(value)
    setLegacyEdge(undefined)
    setFormalEdge(undefined)
    const next = new URLSearchParams(params)
    next.set('source', value)
    setParams(next)
  }

  function selectMetadata(item: FormalMetadataSummary) {
    setSelectedMetadataId(item.metadataId)
    setFormalEdge(undefined)
    const next = new URLSearchParams(params)
    next.set('source', 'formal')
    next.set('metadataId', item.metadataId)
    next.set('asset', formalKeyword)
    setParams(next)
  }

  return (
    <div className="three-panel-grid">
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>血缘图</Typography.Title>
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Segmented
            block
            value={source}
            options={[{ label: '正式元数据', value: 'formal' }, { label: '旧表字段', value: 'legacy' }]}
            onChange={(value) => selectSource(value as LineageSource)}
          />

          {source === 'formal' ? (
            <>
              <Input.Search
                value={formalKeyword}
                placeholder="搜索资产编码/名称"
                allowClear
                onChange={(event) => setFormalKeyword(event.target.value)}
                onSearch={(value) => {
                  setSelectedMetadataId('')
                  setFormalEdge(undefined)
                  updateParam('asset', value)
                }}
              />
              {formalMetadataQuery.isError ? (
                <Alert type="error" showIcon message="正式元数据加载失败" description={(formalMetadataQuery.error as Error).message} />
              ) : null}
              <Spin spinning={formalMetadataQuery.isFetching}>
                <div className="table-list lineage-asset-list">
                  {formalMetadataQuery.data?.items.map((item) => (
                    <button
                      type="button"
                      data-testid={`formal-asset-${item.metadataId}`}
                      className={`table-row ${selectedMetadata?.metadataId === item.metadataId ? 'selected' : ''}`}
                      key={item.metadataId}
                      onClick={() => selectMetadata(item)}
                    >
                      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Typography.Text strong>{item.assetCode}</Typography.Text>
                        <Tag>{item.metadataType}</Tag>
                      </Space>
                      <Typography.Paragraph className="muted" ellipsis={{ rows: 2 }} style={{ margin: '6px 0 0' }}>
                        {item.assetName || '未命名资产'} · {item.sourceType}
                      </Typography.Paragraph>
                    </button>
                  ))}
                </div>
              </Spin>
            </>
          ) : (
            <Input.Search
              value={table}
              placeholder="输入表名"
              onChange={(event) => {
                setTable(event.target.value)
                setLegacyEdge(undefined)
              }}
              onSearch={(value) => {
                setLegacyEdge(undefined)
                updateParam('table', value)
              }}
            />
          )}

          <Segmented
            value={direction}
            options={[{ label: '正向', value: 'down' }, { label: '反向', value: 'up' }]}
            onChange={(value) => {
              setDirection(value as 'up' | 'down')
              setLegacyEdge(undefined)
              setFormalEdge(undefined)
              updateParam('direction', value as string)
            }}
          />
          <Typography.Text className="muted">展开层级: {depth}</Typography.Text>
          <Slider
            min={1}
            max={5}
            value={depth}
            onChange={(value) => {
              setDepth(value)
              setLegacyEdge(undefined)
              setFormalEdge(undefined)
              updateParam('depth', value)
            }}
          />
          <Space wrap>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                if (source === 'formal') formalLineageQuery.refetch()
                else lineageQuery.refetch()
              }}
            >
              刷新
            </Button>
            <Link to={`/chat?context=lineage&table=${source === 'formal' ? selectedMetadata?.assetCode ?? '' : table}`}>
              <Button icon={<CommentOutlined />} type="primary">用 NL 修改</Button>
            </Link>
          </Space>
        </Space>
      </section>

      <section className="panel panel-pad">
        {source === 'formal' ? (
          <>
            {formalLineageQuery.isError ? (
              <Alert
                type="error"
                showIcon
                message="正式血缘加载失败"
                description={(formalLineageQuery.error as Error).message}
                style={{ marginBottom: 12 }}
              />
            ) : null}
            <Spin spinning={formalLineageQuery.isFetching}>
              <FormalLineageGraph
                lineage={formalLineageQuery.data}
                onSelectEdge={(edge, edgeKind) => setFormalEdge({ edge, edgeKind })}
              />
            </Spin>
          </>
        ) : (
          <LineageGraph edges={lineageQuery.data?.edges ?? []} onSelectEdge={setLegacyEdge} />
        )}
      </section>

      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>边详情</Typography.Title>
        {source === 'formal' ? (
          <>
            <Descriptions bordered size="small" column={1} data-testid="formal-current-metadata">
              <Descriptions.Item label="当前资产">{selectedMetadata?.assetCode ?? '未选择'}</Descriptions.Item>
              <Descriptions.Item label="资产名称">{selectedMetadata?.assetName || '未命名资产'}</Descriptions.Item>
              <Descriptions.Item label="metadataId">{selectedMetadata?.metadataId ?? '-'}</Descriptions.Item>
            </Descriptions>
            <div className="lineage-stats">
              <Statistic title="节点" value={formalLineageQuery.data?.nodes.length ?? 0} />
              <Statistic title="资产边" value={formalLineageQuery.data?.edges.length ?? 0} />
              <div data-testid="formal-field-edge-count">
                <Statistic title="字段边" value={formalLineageQuery.data?.fieldEdges.length ?? 0} />
              </div>
            </div>
            <Divider />
            {formalEdge ? (
              <Descriptions bordered size="small" column={1} data-testid="formal-selected-edge">
                <Descriptions.Item label="粒度">{formalEdge.edgeKind === 'field' ? '字段级' : '资产级'}</Descriptions.Item>
                <Descriptions.Item label="上游">{formalEdgeEndpoint(formalEdge.edge, formalEdge.edgeKind, 'source')}</Descriptions.Item>
                <Descriptions.Item label="下游">{formalEdgeEndpoint(formalEdge.edge, formalEdge.edgeKind, 'target')}</Descriptions.Item>
                <Descriptions.Item label="类型">{formalEdge.edge.lineageType}</Descriptions.Item>
                <Descriptions.Item label="方向">{formalEdge.edge.direction}</Descriptions.Item>
                <Descriptions.Item label="表达式">{formalEdge.edge.expression || '未记录'}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Typography.Text className="muted">点击一条正式血缘边查看字段映射和转换表达式</Typography.Text>
            )}
            {formalLineageQuery.data?.fieldEdges.length ? (
              <div className="lineage-edge-list lineage-compact-list">
                {formalLineageQuery.data.fieldEdges.slice(0, 6).map((edge) => (
                  <button
                    type="button"
                    className="lineage-compact-row"
                    key={`${edge.sourceAssetCode}.${edge.sourceField}->${edge.targetAssetCode}.${edge.targetField}`}
                    data-testid={`formal-field-edge-${edge.sourceField}-${edge.targetField}`}
                    onClick={() => setFormalEdge({ edge, edgeKind: 'field' })}
                  >
                    <Tag color="blue">{edge.sourceAssetCode}.{edge.sourceField}</Tag>
                    <span className="muted">→</span>
                    <Tag>{edge.targetAssetCode}.{edge.targetField}</Tag>
                  </button>
                ))}
              </div>
            ) : null}
          </>
        ) : legacyEdge ? (
          <Descriptions bordered size="small" column={1}>
            <Descriptions.Item label="上游">{legacyEdge.from_table}.{legacyEdge.from_field}</Descriptions.Item>
            <Descriptions.Item label="下游">{legacyEdge.to_table}.{legacyEdge.to_field}</Descriptions.Item>
            <Descriptions.Item label="表达式">{legacyEdge.transform_expr || '未记录'}</Descriptions.Item>
          </Descriptions>
        ) : (
          <Typography.Text className="muted">点击一条边查看转换表达式</Typography.Text>
        )}
      </section>
    </div>
  )
}
