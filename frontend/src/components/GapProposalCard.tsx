import { CheckOutlined, EditOutlined, StepForwardOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Space, Typography } from 'antd'

type Props = {
  gaps?: unknown[]
  draft?: unknown
  onConfirm?: () => void
  onCustom?: () => void
  onSkip?: () => void
}

export default function GapProposalCard({ gaps = [], draft, onConfirm, onCustom, onSkip }: Props) {
  return (
    <Card size="small" title="缺失对象补齐建议">
      <Space direction="vertical" style={{ width: '100%' }}>
        <Alert type="warning" showIcon message={`检测到 ${gaps.length || 1} 个元数据缺口`} />
        <Typography.Paragraph className="json-preview">
          {JSON.stringify(draft ?? gaps, null, 2)}
        </Typography.Paragraph>
        <Space wrap>
          <Button type="primary" icon={<CheckOutlined />} onClick={onConfirm}>确认并继续</Button>
          <Button icon={<EditOutlined />} onClick={onCustom}>我自己定义</Button>
          <Button icon={<StepForwardOutlined />} onClick={onSkip}>跳过</Button>
        </Space>
      </Space>
    </Card>
  )
}
