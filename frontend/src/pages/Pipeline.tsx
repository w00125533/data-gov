import { CommentOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Descriptions, Input, Segmented, Slider, Space, Tag, Typography } from 'antd'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import PipelineDAG from '../components/PipelineDAG'
import ReverseSynthesisPanel from '../components/ReverseSynthesisPanel'

export default function Pipeline() {
  const [params, setParams] = useSearchParams()
  const [table, setTable] = useState(params.get('table') ?? '')
  const [mode, setMode] = useState<'forward' | 'reverse'>((params.get('mode') as 'forward' | 'reverse') ?? 'forward')
  const [depth, setDepth] = useState(Number(params.get('depth') ?? 5))
  const [selected, setSelected] = useState<string | undefined>(table || undefined)
  const pipelineQuery = useQuery({
    queryKey: ['pipeline', mode, selected, depth],
    queryFn: () => api.pipeline({ mode, table: selected, depth }),
  })
  const selectedNode = pipelineQuery.data?.nodes.find((node) => node.name === selected)

  function applySearch(value: string) {
    setSelected(value)
    const next = new URLSearchParams(params)
    if (value) next.set('table', value)
    else next.delete('table')
    next.set('mode', mode)
    next.set('depth', String(depth))
    setParams(next)
  }

  return (
    <div className="three-panel-grid">
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>Pipeline 可视化</Typography.Title>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Segmented
            value={mode}
            options={[{ label: '正向 ETL', value: 'forward' }, { label: '反向合成', value: 'reverse' }]}
            onChange={(value) => {
              setMode(value as 'forward' | 'reverse')
              const next = new URLSearchParams(params)
              next.set('mode', value as string)
              next.set('depth', String(depth))
              setParams(next)
            }}
          />
          <Input.Search
            value={table}
            placeholder="搜索表名"
            onChange={(event) => setTable(event.target.value)}
            onSearch={applySearch}
          />
          <Typography.Text className="muted">展开层级: {depth}</Typography.Text>
          <Slider
            min={1}
            max={5}
            value={depth}
            onChange={(value) => {
              setDepth(value)
              const next = new URLSearchParams(params)
              next.set('depth', String(value))
              setParams(next)
            }}
          />
          {pipelineQuery.data?.selected_path.length ? (
            <Space wrap>
              {pipelineQuery.data.selected_path.map((item) => <Tag key={item}>{item}</Tag>)}
            </Space>
          ) : null}
        </Space>
      </section>
      <section className="panel panel-pad">
        <PipelineDAG payload={pipelineQuery.data} onSelectTable={setSelected} />
      </section>
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>表信息</Typography.Title>
        {selectedNode ? (
          <>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="表名">{selectedNode.name}</Descriptions.Item>
              <Descriptions.Item label="层级">{selectedNode.layer}</Descriptions.Item>
              <Descriptions.Item label="存储">{selectedNode.storage_type}</Descriptions.Item>
              <Descriptions.Item label="字段数">{selectedNode.field_count}</Descriptions.Item>
              <Descriptions.Item label="描述">{selectedNode.description}</Descriptions.Item>
              <Descriptions.Item label="上游">{selectedNode.upstream_tables?.join(', ') || '-'}</Descriptions.Item>
              <Descriptions.Item label="下游">{selectedNode.downstream_tables?.join(', ') || '-'}</Descriptions.Item>
            </Descriptions>
            <Link to={`/chat?context=pipeline&table=${selectedNode.name}&mode=${mode}`}>
              <Button style={{ marginTop: 12 }} type="primary" icon={<CommentOutlined />}>NL 查询</Button>
            </Link>
            {mode === 'reverse' ? (
              <div style={{ marginTop: 16 }}>
                <Typography.Title level={5}>约束反推</Typography.Title>
                <ReverseSynthesisPanel constraints={pipelineQuery.data?.constraints ?? []} />
              </div>
            ) : null}
          </>
        ) : (
          <Typography.Text className="muted">选择图中表节点查看详情</Typography.Text>
        )}
      </section>
    </div>
  )
}
