import { CommentOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Descriptions, Input, Segmented, Space, Typography } from 'antd'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import PipelineDAG from '../components/PipelineDAG'

export default function Pipeline() {
  const [params, setParams] = useSearchParams()
  const [table, setTable] = useState(params.get('table') ?? '')
  const [mode, setMode] = useState<'forward' | 'reverse'>((params.get('mode') as 'forward' | 'reverse') ?? 'forward')
  const [selected, setSelected] = useState<string | undefined>(table || undefined)
  const pipelineQuery = useQuery({
    queryKey: ['pipeline', mode, selected],
    queryFn: () => api.pipeline({ mode, table: selected }),
  })
  const selectedNode = pipelineQuery.data?.nodes.find((node) => node.name === selected)

  return (
    <div className="three-panel-grid">
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>Pipeline 可视化</Typography.Title>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Segmented
            value={mode}
            options={[{ label: '正向 ETL', value: 'forward' }, { label: '反向合成', value: 'reverse' }]}
            onChange={(value) => setMode(value as 'forward' | 'reverse')}
          />
          <Input.Search
            value={table}
            placeholder="搜索表名"
            onChange={(event) => setTable(event.target.value)}
            onSearch={(value) => {
              setSelected(value)
              params.set('table', value)
              params.set('mode', mode)
              setParams(params)
            }}
          />
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
            </Descriptions>
            <Link to={`/chat?context=pipeline&table=${selectedNode.name}&mode=${mode}`}>
              <Button style={{ marginTop: 12 }} type="primary" icon={<CommentOutlined />}>NL 查询</Button>
            </Link>
          </>
        ) : (
          <Typography.Text className="muted">选择图中表节点查看详情</Typography.Text>
        )}
      </section>
    </div>
  )
}
