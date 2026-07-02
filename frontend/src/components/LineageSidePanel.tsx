import { DeleteOutlined, EditOutlined, MessageOutlined } from '@ant-design/icons'
import { Button, Descriptions, Space, Typography } from 'antd'
import type { LineageEdge } from '../api/client'

type Props = {
  edge?: LineageEdge
  nodeId?: string
  onEditEdge?: () => void
  onDeleteEdge?: () => void
  onChat?: () => void
}

export default function LineageSidePanel({ edge, nodeId, onEditEdge, onDeleteEdge, onChat }: Props) {
  if (edge) {
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="上游">{edge.from_table}.{edge.from_field}</Descriptions.Item>
          <Descriptions.Item label="下游">{edge.to_table}.{edge.to_field}</Descriptions.Item>
          <Descriptions.Item label="表达式">{edge.transform_expr || '未记录'}</Descriptions.Item>
        </Descriptions>
        <Space wrap>
          <Button icon={<EditOutlined />} onClick={onEditEdge}>编辑</Button>
          <Button danger icon={<DeleteOutlined />} onClick={onDeleteEdge}>删除</Button>
          <Button type="primary" icon={<MessageOutlined />} onClick={onChat}>NL 修改</Button>
        </Space>
      </Space>
    )
  }
  if (nodeId) {
    const [table, field] = nodeId.split('.')
    return (
      <Descriptions bordered size="small" column={1}>
        <Descriptions.Item label="表">{table}</Descriptions.Item>
        <Descriptions.Item label="字段">{field ?? '-'}</Descriptions.Item>
      </Descriptions>
    )
  }
  return <Typography.Text className="muted">选择节点或边查看详情</Typography.Text>
}
