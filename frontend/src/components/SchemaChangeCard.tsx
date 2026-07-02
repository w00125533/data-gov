import { DiffOutlined, ForkOutlined } from '@ant-design/icons'
import { Button, Card, Space, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'
import type { SchemaChange } from '../api/client'

type Props = {
  change: SchemaChange
  onYamlDiff?: (change: SchemaChange) => void
}

function compactValue(value: unknown) {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

export default function SchemaChangeCard({ change, onYamlDiff }: Props) {
  const target = change.table_name ? `${change.table_name}${change.field_name ? `.${change.field_name}` : ''}` : change.field_name || 'table'
  return (
    <Card size="small" className="schema-change-card">
      <Space direction="vertical" style={{ width: '100%' }} size={8}>
        <Space wrap>
          <Tag>{change.operation}</Tag>
          <Typography.Text strong>{target}</Typography.Text>
          {change.version ? <Tag color="blue">v{change.previous_version ?? '-'} → v{change.version}</Tag> : null}
        </Space>
        <div className="inline-diff">
          <Typography.Text className="muted">旧: {compactValue(change.old_value)}</Typography.Text>
          <Typography.Text>新: {compactValue(change.new_value)}</Typography.Text>
        </div>
        {change.downstream?.length ? (
          <Space wrap>
            <Typography.Text className="muted">影响下游</Typography.Text>
            {change.downstream.map((item, index) => (
              <Tag color="warning" key={`${item.table}.${item.field}-${index}`}>{item.table}.{item.field}</Tag>
            ))}
          </Space>
        ) : null}
        <Space wrap>
          <Button size="small" icon={<DiffOutlined />} onClick={() => onYamlDiff?.(change)}>查看 YAML diff</Button>
          {change.table_name ? (
            <Link to={`/metadata/lineage?table=${change.table_name}`}>
              <Button size="small" icon={<ForkOutlined />}>查看血缘</Button>
            </Link>
          ) : null}
        </Space>
      </Space>
    </Card>
  )
}
