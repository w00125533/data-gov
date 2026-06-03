import { CheckCircleOutlined } from '@ant-design/icons'
import { Alert, Table } from 'antd'

type Props = {
  row?: Record<string, unknown>
}

export default function DryRunPreview({ row }: Props) {
  if (!row) return <Alert type="info" message="等待沙箱试跑结果" showIcon />
  const columns = Object.keys(row).map((key) => ({ title: key, dataIndex: key, key }))
  return (
    <>
      <Alert type="success" message="Dry-run 成功" icon={<CheckCircleOutlined />} showIcon />
      <Table size="small" rowKey={() => 'preview'} columns={columns} dataSource={[row]} pagination={false} />
    </>
  )
}
