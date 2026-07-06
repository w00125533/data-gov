import { ReloadOutlined, SyncOutlined } from '@ant-design/icons'
import { Alert, Button, Space, Typography } from 'antd'
import type { ReactNode } from 'react'
import type { LineageSqlPreviewResponse } from '../api/client'

type Props = {
  preview?: LineageSqlPreviewResponse
  loading?: boolean
  onRefresh: () => void
  onSync: () => void
  workflowActions?: ReactNode
}

export default function LineageSqlPanel({ preview, loading, onRefresh, onSync, workflowActions }: Props) {
  const sql = preview?.sql ?? ''

  return (
    <Space className="lineage-sql-panel" orientation="vertical" style={{ width: '100%' }} size="middle">
      <Space orientation="vertical" style={{ width: '100%' }} size="small">
        <Typography.Title level={5} style={{ margin: 0 }}>
          SQL 逻辑
        </Typography.Title>
        <Space wrap>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={onRefresh}>
            生成 SQL
          </Button>
          <Button type="primary" icon={<SyncOutlined />} disabled={!sql} onClick={onSync}>
            同步到表定义
          </Button>
        </Space>
        {workflowActions ? (
          <Space className="lineage-sql-workflow-actions" wrap>
            {workflowActions}
          </Space>
        ) : null}
      </Space>
      <pre className="json-preview">
        {sql || '暂无 SQL 预览'}
      </pre>
      {preview?.warnings?.map((warning) => (
        <Alert key={warning} type="warning" showIcon title={warning} />
      ))}
      {preview?.changed ? <Alert type="info" showIcon title="生成 SQL 与当前表定义不一致" /> : null}
    </Space>
  )
}
