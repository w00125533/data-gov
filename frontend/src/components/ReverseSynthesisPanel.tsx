import { Card, Space, Typography } from 'antd'
import ConstraintSlider from './ConstraintSlider'

type Constraint = {
  field: string
  range: [number, number] | number[]
  rows: number
  bucket: string
}

type Props = {
  constraints?: Constraint[]
  onChange?: (constraints: Constraint[]) => void
}

export default function ReverseSynthesisPanel({ constraints = [], onChange }: Props) {
  function update(index: number, patch: Partial<Constraint>) {
    const next = constraints.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item)
    onChange?.(next)
  }

  if (!constraints.length) {
    return <Typography.Text className="muted">暂无反向约束</Typography.Text>
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {constraints.map((constraint, index) => (
        <Card size="small" key={`${constraint.field}-${constraint.bucket}`}>
          <ConstraintSlider
            label={`${constraint.field} · ${constraint.bucket}`}
            value={[Number(constraint.range[0]), Number(constraint.range[1])]}
            rows={constraint.rows}
            onRangeChange={(range) => update(index, { range })}
            onRowsChange={(rows) => update(index, { rows })}
          />
          <div className="bucket-bar" style={{ width: `${Math.min(100, constraint.rows * 12)}%` }} />
        </Card>
      ))}
    </Space>
  )
}
