import { Badge, Card, Col, Row, Typography } from 'antd'
import type { HealthPayload } from '../api/client'

type Props = {
  payload?: HealthPayload
}

export default function HealthPanel({ payload }: Props) {
  const components = payload?.components ? Object.entries(payload.components) : []
  return (
    <Row gutter={[12, 12]}>
      <Col xs={24} md={8}>
        <Card size="small">
          <Badge status={payload?.status === 'healthy' ? 'success' : 'processing'} text="FastAPI" />
          <Typography.Paragraph className="muted" style={{ marginBottom: 0 }}>
            {payload?.status ?? 'checking'}
          </Typography.Paragraph>
        </Card>
      </Col>
      {components.map(([name, component]) => (
        <Col xs={24} md={8} key={name}>
          <Card size="small">
            <Badge status={component.status === 'healthy' ? 'success' : 'error'} text={name} />
            <Typography.Paragraph className="muted" style={{ marginBottom: 0 }}>
              {component.detail || component.status}
            </Typography.Paragraph>
          </Card>
        </Col>
      ))}
    </Row>
  )
}
