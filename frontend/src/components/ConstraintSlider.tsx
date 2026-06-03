import { InputNumber, Slider, Space, Typography } from 'antd'

type Props = {
  label: string
  value: [number, number]
  rows: number
}

export default function ConstraintSlider({ label, value, rows }: Props) {
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
        <Typography.Text strong>{label}</Typography.Text>
        <InputNumber size="small" value={rows} min={1} />
      </Space>
      <Slider range min={0} max={100} value={value} />
    </Space>
  )
}
