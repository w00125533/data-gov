import { Steps } from 'antd'

const labels: Record<string, string> = {
  classifier: '意图识别',
  forward_etl: '正向 ETL',
  reverse_synth: '反向合成',
  schema_evolve: '元数据演进',
  schema_lookup: 'Schema 查询',
  gap_check: '缺口检测',
  gap_proposal: '补齐建议',
  code_generate: '代码生成',
  dry_run: '沙箱试跑',
  presenter: '结果汇总',
}

type Props = {
  nodes: string[]
}

export default function AgentStepper({ nodes }: Props) {
  const uniqueNodes = Array.from(new Set(nodes))
  return (
    <Steps
      size="small"
      direction="vertical"
      current={Math.max(uniqueNodes.length - 1, 0)}
      items={uniqueNodes.map((node) => ({ title: labels[node] ?? node, status: 'finish' }))}
    />
  )
}
