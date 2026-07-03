import { DeleteOutlined, SaveOutlined } from '@ant-design/icons'
import { Alert, Button, Form, Input, Select, Space, Typography } from 'antd'
import { useEffect } from 'react'
import type { CalcType, LineageEdge } from '../api/client'

type Props = {
  edge?: LineageEdge
  saving?: boolean
  onSave: (edge: LineageEdge) => void
  onDelete: () => void
}

type FormValues = {
  calc_type?: CalcType
  transform_expr?: string
  calc_params?: string
}

const calcTypeOptions: CalcType[] = ['DIRECT', 'EXPRESSION', 'AGGREGATE', 'JOIN', 'WINDOW', 'CONDITION', 'CONSTANT']

export default function LineageEdgeEditor({ edge, saving, onSave, onDelete }: Props) {
  if (!edge) {
    return <Alert type="info" showIcon title="请选择一条字段级血缘边" />
  }

  return (
    <SelectedLineageEdgeEditor
      edge={edge}
      saving={saving}
      onSave={onSave}
      onDelete={onDelete}
    />
  )
}

function SelectedLineageEdgeEditor({ edge, saving, onSave, onDelete }: Required<Pick<Props, 'edge' | 'onSave' | 'onDelete'>> & Pick<Props, 'saving'>) {
  const [form] = Form.useForm<FormValues>()

  useEffect(() => {
    form.setFieldsValue({
      calc_type: edge.calc_type ?? 'DIRECT',
      transform_expr: edge.transform_expr,
      calc_params: JSON.stringify(edge.calc_params ?? {}, null, 2),
    })
  }, [edge, form])

  function submit(values: FormValues) {
    let calcParams: Record<string, unknown> | undefined
    try {
      calcParams = values.calc_params?.trim()
        ? JSON.parse(values.calc_params) as Record<string, unknown>
        : {}
      if (!calcParams || Array.isArray(calcParams) || typeof calcParams !== 'object') {
        form.setFields([
          {
            name: 'calc_params',
            errors: ['计算参数 JSON 必须是对象'],
          },
        ])
        return
      }
    } catch {
      form.setFields([
        {
          name: 'calc_params',
          errors: ['计算参数必须是合法 JSON'],
        },
      ])
      return
    }

    onSave({
      ...edge,
      calc_type: values.calc_type,
      transform_expr: values.transform_expr ?? '',
      calc_params: calcParams,
    })
  }

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      <Typography.Title level={5} style={{ margin: 0 }}>边计算配置</Typography.Title>
      <Typography.Text className="muted">
        {edge.from_table}.{edge.from_field} → {edge.to_table}.{edge.to_field}
      </Typography.Text>
      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item label="计算类型" name="calc_type">
          <Select options={calcTypeOptions.map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item
          label="转换表达式"
          name="transform_expr"
          rules={[
            { required: true, whitespace: true, message: '请输入转换表达式' },
          ]}
        >
          <Input.TextArea rows={3} />
        </Form.Item>
        <Form.Item label="计算参数 JSON" name="calc_params">
          <Input.TextArea rows={5} spellCheck={false} />
        </Form.Item>
        <Space wrap>
          <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
            保存边配置
          </Button>
          <Button danger icon={<DeleteOutlined />} onClick={onDelete}>
            删除血缘边
          </Button>
        </Space>
      </Form>
    </Space>
  )
}
