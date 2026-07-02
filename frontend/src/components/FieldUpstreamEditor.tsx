import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Select, Space, Tag, Typography } from 'antd'
import { useMemo, useState } from 'react'
import { api, type UpstreamRef } from '../api/client'

type Props = {
  value?: UpstreamRef[]
  onChange?: (value: UpstreamRef[]) => void
}

export default function FieldUpstreamEditor({ value = [], onChange }: Props) {
  const [table, setTable] = useState<string>()
  const [field, setField] = useState<string>()
  const tablesQuery = useQuery({ queryKey: ['tables', 'upstream-editor'], queryFn: () => api.tables() })
  const selectedTable = useMemo(
    () => tablesQuery.data?.find((item) => item.name === table),
    [table, tablesQuery.data],
  )
  const detailQuery = useQuery({
    queryKey: ['table', selectedTable?.id, 'upstream-editor'],
    queryFn: () => api.table(selectedTable!.id),
    enabled: Boolean(selectedTable?.id),
  })

  function addRef() {
    if (!table || !field) return
    const next = [...value]
    if (!next.some((item) => item.table === table && item.field === field)) {
      next.push({ table, field })
      onChange?.(next)
    }
    setField(undefined)
  }

  function removeRef(ref: UpstreamRef) {
    onChange?.(value.filter((item) => !(item.table === ref.table && item.field === ref.field)))
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space wrap>
        <Select
          showSearch
          allowClear
          placeholder="源表"
          value={table}
          onChange={(next) => {
            setTable(next)
            setField(undefined)
          }}
          options={tablesQuery.data?.map((item) => ({ value: item.name, label: item.name }))}
          style={{ width: 220 }}
        />
        <Select
          showSearch
          allowClear
          placeholder="源字段"
          value={field}
          disabled={!table}
          onChange={setField}
          options={detailQuery.data?.fields.map((item) => ({ value: item.name, label: item.name }))}
          style={{ width: 180 }}
        />
        <Button icon={<PlusOutlined />} onClick={addRef} disabled={!table || !field}>
          添加
        </Button>
      </Space>
      <Space wrap>
        {value.length ? value.map((ref) => (
          <Tag
            key={`${ref.table}.${ref.field}`}
            closable
            closeIcon={<DeleteOutlined />}
            onClose={(event) => {
              event.preventDefault()
              removeRef(ref)
            }}
          >
            {ref.table}.{ref.field}
          </Tag>
        )) : <Typography.Text className="muted">无上游字段</Typography.Text>}
      </Space>
    </Space>
  )
}
