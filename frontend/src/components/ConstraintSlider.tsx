import { InputNumber, Slider, Space, Typography } from 'antd'

type Props = {
  label: string
  value: [number, number]
  rows: number
  onRangeChange?: (value: [number, number]) => void
  onRowsChange?: (value: number) => void
}

export default function ConstraintSlider({ label, value, rows, onRangeChange, onRowsChange }: Props) {
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
        <Typography.Text strong>{label}</Typography.Text>
        <InputNumber size="small" value={rows} min={1} onChange={(next) => onRowsChange?.(Number(next ?? 1))} />
      </Space>
      <Slider range min={0} max={100} value={value} onChange={(next) => onRangeChange?.(next as [number, number])} />
    </Space>
  )
}
