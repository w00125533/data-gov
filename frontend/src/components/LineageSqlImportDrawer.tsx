import { Alert, Button, Drawer, Input, Space, Typography } from 'antd'
import { useState } from 'react'
import type { LineageSqlImportPreviewResponse } from '../api/client'

type Props = {
  open: boolean
  loading?: boolean
  preview?: LineageSqlImportPreviewResponse
  onClose: () => void
  onPreview: (sql: string) => void
  onApply: () => void
}

export default function LineageSqlImportDrawer({ open, loading, preview, onClose, onPreview, onApply }: Props) {
  const [sql, setSql] = useState('')

  return (
    <Drawer title="导入 SQL" open={open} size="large" onClose={onClose}>
      <Space orientation="vertical" style={{ width: '100%' }}>
        <Input.TextArea
          aria-label="SQL 文本"
          rows={8}
          value={sql}
          onChange={(event) => setSql(event.target.value)}
        />
        <Button type="primary" loading={loading} onClick={() => onPreview(sql)}>
          解析 SQL
        </Button>
        {preview?.warnings.map((warning) => (
          <Alert key={warning} type="warning" message={warning} showIcon />
        ))}
        {preview ? (
          <>
            <Typography.Title level={5}>字段变更</Typography.Title>
            <Space orientation="vertical" size={4} style={{ width: '100%' }}>
              {preview.fields.map((field) => (
                <Typography.Text key={`${field.action}-${field.field}-${field.expression}`}>
                  {field.action} | {field.field} | {field.expression}
                </Typography.Text>
              ))}
            </Space>
            <Typography.Title level={5}>血缘变更</Typography.Title>
            <Space orientation="vertical" size={4} style={{ width: '100%' }}>
              {preview.edges.map((edge) => (
                <Typography.Text key={`${edge.action}-${edge.edge.from_table}-${edge.edge.from_field}-${edge.edge.to_table}-${edge.edge.to_field}`}>
                  {edge.action} | {edge.edge.from_table}.{edge.edge.from_field} -&gt; {edge.edge.to_table}.{edge.edge.to_field}
                </Typography.Text>
              ))}
            </Space>
            <Button type="primary" loading={loading} onClick={onApply}>
              确认应用
            </Button>
          </>
        ) : null}
      </Space>
    </Drawer>
  )
}
