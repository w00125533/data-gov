import { CommentOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Descriptions, Input, Segmented, Slider, Space, Typography } from 'antd'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, type LineageEdge } from '../api/client'
import LineageGraph from '../components/LineageGraph'

export default function Lineage() {
  const [params, setParams] = useSearchParams()
  const [table, setTable] = useState(params.get('table') ?? 'dws_cell_hourly')
  const [direction, setDirection] = useState<'up' | 'down'>((params.get('direction') as 'up' | 'down') ?? 'down')
  const [depth, setDepth] = useState(Number(params.get('depth') ?? 5))
  const [edge, setEdge] = useState<LineageEdge | undefined>()

  const lineageQuery = useQuery({
    queryKey: ['lineage', table, direction, depth],
    queryFn: () => api.lineage({ table, direction, depth }),
  })

  return (
    <div className="three-panel-grid">
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>字段级血缘</Typography.Title>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input.Search
            value={table}
            onChange={(event) => setTable(event.target.value)}
            onSearch={(value) => {
              params.set('table', value)
              setParams(params)
            }}
          />
          <Segmented
            value={direction}
            options={[{ label: '正向', value: 'down' }, { label: '反向', value: 'up' }]}
            onChange={(value) => setDirection(value as 'up' | 'down')}
          />
          <Typography.Text className="muted">展开层级: {depth}</Typography.Text>
          <Slider min={1} max={5} value={depth} onChange={setDepth} />
          <Link to={`/chat?context=lineage&table=${table}`}>
            <Button icon={<CommentOutlined />} type="primary">用 NL 修改</Button>
          </Link>
        </Space>
      </section>
      <section className="panel panel-pad">
        <LineageGraph edges={lineageQuery.data?.edges ?? []} onSelectEdge={setEdge} />
      </section>
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>边详情</Typography.Title>
        {edge ? (
          <Descriptions bordered size="small" column={1}>
            <Descriptions.Item label="上游">{edge.from_table}.{edge.from_field}</Descriptions.Item>
            <Descriptions.Item label="下游">{edge.to_table}.{edge.to_field}</Descriptions.Item>
            <Descriptions.Item label="表达式">{edge.transform_expr || '未记录'}</Descriptions.Item>
          </Descriptions>
        ) : (
          <Typography.Text className="muted">点击一条边查看转换表达式</Typography.Text>
        )}
      </section>
    </div>
  )
}
