import { useQuery } from '@tanstack/react-query'
import { Typography } from 'antd'
import { api } from '../api/client'
import HealthPanel from '../components/HealthPanel'

export default function Health() {
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 30_000,
  })

  return (
    <section className="panel panel-pad">
      <Typography.Title level={3} style={{ marginTop: 0 }}>健康检查</Typography.Title>
      <Typography.Paragraph className="muted">每 30 秒自动刷新 FastAPI 与基础设施连通性。</Typography.Paragraph>
      <HealthPanel payload={healthQuery.data} />
    </section>
  )
}
