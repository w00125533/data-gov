import { useQuery } from '@tanstack/react-query'
import { Button, Input, Modal, Select, Space, Typography } from 'antd'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, type SchemaChange } from '../api/client'
import DiffPanel from '../components/DiffPanel'
import EvolutionTimeline from '../components/EvolutionTimeline'

const operations = [
  'ALL',
  'ADD_TABLE',
  'ADD_FIELD',
  'UPDATE_FIELD',
  'DELETE_FIELD',
  'table_create',
  'table_classification_update',
  'category_create',
  'category_update',
  'category_move',
  'category_status_update',
  'tag_group_create',
  'tag_group_update',
  'tag_create',
  'tag_update',
  'tag_status_update',
]

export default function SchemaEvolution() {
  const [params, setParams] = useSearchParams()
  const [table, setTable] = useState(params.get('table') ?? '')
  const [operation, setOperation] = useState(params.get('operation') ?? 'ALL')
  const [keyword, setKeyword] = useState(params.get('q') ?? '')
  const [selected, setSelected] = useState<SchemaChange | undefined>()
  const effectiveTable = table.trim() || undefined

  const evolutionQuery = useQuery({
    queryKey: ['schema-evolution-list', effectiveTable, operation, keyword],
    queryFn: () => api.schemaEvolutionList({
      table: effectiveTable,
      operation: operation === 'ALL' ? undefined : operation,
      q: keyword.trim() || undefined,
    }),
  })
  const selectedTable = selected?.table_name ?? effectiveTable
  const diffQuery = useQuery({
    queryKey: ['yaml-diff', selectedTable, selected?.version, selected?.change_id],
    queryFn: () => api.yamlDiff(selectedTable!, selected?.version ?? 1),
    enabled: Boolean(selectedTable && selected),
  })

  function applyFilters() {
    if (effectiveTable) params.set('table', effectiveTable)
    else params.delete('table')
    if (operation !== 'ALL') params.set('operation', operation)
    else params.delete('operation')
    if (keyword.trim()) params.set('q', keyword.trim())
    else params.delete('q')
    setParams(params)
  }

  return (
    <div className="page-grid">
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>演化历史</Typography.Title>
        <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
          <Input value={table} placeholder="表名，可留空查看全部" onChange={(event) => setTable(event.target.value)} />
          <Select value={operation} options={operations.map((value) => ({ value, label: value === 'ALL' ? '全部操作' : value }))} onChange={setOperation} />
          <Input.Search value={keyword} placeholder="表名/字段关键词" onChange={(event) => setKeyword(event.target.value)} onSearch={applyFilters} />
          <Button type="primary" onClick={applyFilters}>应用过滤</Button>
        </Space>
        <EvolutionTimeline changes={evolutionQuery.data?.changes ?? []} onSelect={setSelected} />
      </section>
      <section className="panel panel-pad">
        <Typography.Title level={4} style={{ marginTop: 0 }}>{effectiveTable ?? '全部表'}</Typography.Title>
        <Typography.Paragraph className="muted">
          按时间倒序查看 Change 节点记录，支持按表、字段关键词和操作类型过滤。
        </Typography.Paragraph>
        {effectiveTable ? (
          <Link to={`/metadata/lineage?table=${effectiveTable}`}>
            <Button>查看血缘</Button>
          </Link>
        ) : null}
      </section>
      <Modal
        title="YAML diff"
        open={Boolean(selected)}
        onCancel={() => setSelected(undefined)}
        footer={null}
        width={980}
      >
        <DiffPanel
          oldValue={diffQuery.data?.historical ?? ''}
          newValue={diffQuery.data?.current ?? ''}
          oldLabel={`历史版本 v${selected?.previous_version ?? '-'}`}
          newLabel={`当前版本 v${selected?.version ?? '-'}`}
        />
      </Modal>
    </div>
  )
}
