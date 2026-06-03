import {
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  ForkOutlined,
  HistoryOutlined,
  PlusOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Button,
  Checkbox,
  Descriptions,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  api,
  type CreateFieldPayload,
  type CreateTablePayload,
  type FieldResponse,
  type Layer,
  type TableResponse,
  type TableSummary,
  type UpdateFieldPayload,
} from '../api/client'

const layers: Array<Layer | 'ALL'> = ['ALL', 'ODS', 'DWD', 'DWS', 'ADS', 'EVAL']
const fieldTypes = ['STRING', 'INT', 'BIGINT', 'DOUBLE', 'TIMESTAMP', 'DATE']
const storageTypes = ['KAFKA', 'HIVE', 'STARROCKS']

type TableFormValues = CreateTablePayload & {
  fields?: Array<{
    name?: string
    data_type?: string
    nullable?: boolean
    partition?: boolean
    expression?: string
    description?: string
  }>
}

type FieldFormValues = {
  name?: string
  field_type: string
  is_nullable: boolean
  is_partition: boolean
  expression?: string
  description: string
  upstream_text?: string
}

function parseUpstream(text?: string) {
  return (text ?? '')
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const [table, field] = item.split('.')
      return { table, field }
    })
    .filter((item) => item.table && item.field)
}

function upstreamText(field?: FieldResponse) {
  return field?.upstream.map((up) => `${up.table}.${up.field}`).join('\n') ?? ''
}

export default function Metadata() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [apiMessage, holder] = message.useMessage()
  const [layer, setLayer] = useState<string>(params.get('layer') ?? 'ALL')
  const [search, setSearch] = useState(params.get('search') ?? '')
  const [selected, setSelected] = useState<TableSummary | undefined>()
  const [yamlTable, setYamlTable] = useState<string | undefined>()
  const [tableModal, setTableModal] = useState<'create' | 'edit' | undefined>()
  const [fieldDrawer, setFieldDrawer] = useState<{ mode: 'create' | 'edit'; field?: FieldResponse } | undefined>()
  const [tableForm] = Form.useForm<TableFormValues>()
  const [fieldForm] = Form.useForm<FieldFormValues>()

  const tableQuery = useQuery({
    queryKey: ['tables', layer, search],
    queryFn: () => api.tables({ layer: layer === 'ALL' ? undefined : layer, search }),
  })

  const selectedTable = selected ?? tableQuery.data?.[0]
  const detailQuery = useQuery({
    queryKey: ['table', selectedTable?.id],
    queryFn: () => api.table(selectedTable!.id),
    enabled: Boolean(selectedTable?.id),
  })

  const yamlQuery = useQuery({
    queryKey: ['yaml-preview', yamlTable],
    queryFn: () => api.yamlPreview(yamlTable!),
    enabled: Boolean(yamlTable),
  })

  function refreshMetadata(table?: TableResponse) {
    queryClient.invalidateQueries({ queryKey: ['tables'] })
    if (table?.id) {
      setSelected(table)
      queryClient.invalidateQueries({ queryKey: ['table', table.id] })
    } else if (selectedTable?.id) {
      queryClient.invalidateQueries({ queryKey: ['table', selectedTable.id] })
    }
  }

  const createTableMutation = useMutation({
    mutationFn: api.createTable,
    onSuccess: (table) => {
      apiMessage.success('表已创建')
      setTableModal(undefined)
      tableForm.resetFields()
      refreshMetadata(table)
    },
    onError: (error) => apiMessage.error(`创建失败: ${(error as Error).message}`),
  })

  const updateTableMutation = useMutation({
    mutationFn: (values: TableFormValues) => api.updateTable(detailQuery.data!.id, values),
    onSuccess: (table) => {
      apiMessage.success('表信息已更新')
      setTableModal(undefined)
      refreshMetadata(table)
    },
    onError: (error) => apiMessage.error(`更新失败: ${(error as Error).message}`),
  })

  const schemaApplyMutation = useMutation({
    mutationFn: api.applySchema,
    onSuccess: (payload) => {
      if (payload.passed) {
        apiMessage.success('已保存并同步 YAML')
        setTableModal(undefined)
        tableForm.resetFields()
        queryClient.invalidateQueries({ queryKey: ['tables'] })
      } else {
        apiMessage.warning(`校验未通过: ${JSON.stringify(payload.errors)}`)
      }
    },
    onError: (error) => apiMessage.error(`同步失败: ${(error as Error).message}`),
  })

  const createFieldMutation = useMutation({
    mutationFn: api.createField,
    onSuccess: () => {
      apiMessage.success('字段已创建')
      setFieldDrawer(undefined)
      refreshMetadata()
    },
    onError: (error) => apiMessage.error(`字段创建失败: ${(error as Error).message}`),
  })

  const updateFieldMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateFieldPayload }) => api.updateField(id, payload),
    onSuccess: () => {
      apiMessage.success('字段已更新')
      setFieldDrawer(undefined)
      refreshMetadata()
    },
    onError: (error) => apiMessage.error(`字段更新失败: ${(error as Error).message}`),
  })

  const deleteFieldMutation = useMutation({
    mutationFn: api.deleteField,
    onSuccess: () => {
      apiMessage.success('字段已删除')
      refreshMetadata()
    },
    onError: (error) => apiMessage.error(`删除被拒绝: ${(error as Error).message}`),
  })

  const deleteTableMutation = useMutation({
    mutationFn: api.deleteTable,
    onSuccess: () => {
      apiMessage.success('表已删除')
      setSelected(undefined)
      queryClient.invalidateQueries({ queryKey: ['tables'] })
    },
    onError: (error) => apiMessage.error(`删除被拒绝: ${(error as Error).message}`),
  })

  const columns = useMemo<ColumnsType<FieldResponse>>(
    () => [
      {
        title: '字段',
        dataIndex: 'name',
        render: (name, row) => (
          <Tooltip
            title={
              row.upstream.length
                ? row.upstream.map((up) => `${up.table}.${up.field}`).join(', ')
                : '无上游字段'
            }
          >
            <Typography.Text strong={row.is_partition}>{name}</Typography.Text>
          </Tooltip>
        ),
      },
      { title: '类型', dataIndex: 'field_type', width: 110 },
      {
        title: '上游',
        dataIndex: 'upstream',
        render: (value: FieldResponse['upstream']) =>
          value.length
            ? value.map((up) => <Tag key={`${up.table}.${up.field}`}>{up.table}.{up.field}</Tag>)
            : <span className="muted">无</span>,
      },
      { title: '表达式', dataIndex: 'expression', ellipsis: true },
      { title: '版本', dataIndex: 'version', width: 80 },
      {
        title: '操作',
        width: 118,
        render: (_, row) => (
          <Space size={4}>
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                fieldForm.setFieldsValue({
                  name: row.name,
                  field_type: row.field_type,
                  is_nullable: row.is_nullable,
                  is_partition: row.is_partition,
                  expression: row.expression ?? '',
                  description: row.description,
                  upstream_text: upstreamText(row),
                })
                setFieldDrawer({ mode: 'edit', field: row })
              }}
            />
            <Popconfirm title="删除字段" description="有下游依赖时后端会拒绝删除。" onConfirm={() => deleteFieldMutation.mutate(row.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [deleteFieldMutation, fieldForm],
  )

  function openCreateTable() {
    tableForm.resetFields()
    tableForm.setFieldsValue({
      layer: 'ODS',
      storage_type: 'HIVE',
      description: '',
      fields: [{ data_type: 'STRING', nullable: true, partition: false }],
    })
    setTableModal('create')
  }

  function openEditTable() {
    if (!detailQuery.data) return
    tableForm.setFieldsValue({
      name: detailQuery.data.name,
      layer: detailQuery.data.layer,
      storage_type: detailQuery.data.storage_type as CreateTablePayload['storage_type'],
      description: detailQuery.data.description,
    })
    setTableModal('edit')
  }

  function submitTable(saveAndExport: boolean) {
    tableForm.validateFields().then((values) => {
      if (tableModal === 'edit') {
        updateTableMutation.mutate(values)
        return
      }
      if (saveAndExport) {
        schemaApplyMutation.mutate({
          diff: [
            {
              operation: 'ADD_TABLE',
              table: values.name,
              layer: values.layer,
              storage_type: values.storage_type,
              description: values.description,
              fields: (values.fields ?? [])
                .filter((field) => field.name)
                .map((field) => ({
                  name: field.name,
                  data_type: field.data_type ?? 'STRING',
                  nullable: field.nullable ?? true,
                  partition: field.partition ?? false,
                  expression: field.expression,
                  description: field.description ?? '',
                  upstream: [],
                })),
            },
          ],
        })
        return
      }
      createTableMutation.mutate({
        name: values.name,
        layer: values.layer,
        storage_type: values.storage_type,
        description: values.description,
      })
    })
  }

  function submitField() {
    if (!detailQuery.data) return
    fieldForm.validateFields().then((values) => {
      const basePayload = {
        field_type: values.field_type,
        is_nullable: values.is_nullable,
        is_partition: values.is_partition,
        expression: values.expression || null,
        description: values.description,
        upstream: parseUpstream(values.upstream_text),
      }
      if (fieldDrawer?.mode === 'edit' && fieldDrawer.field) {
        updateFieldMutation.mutate({ id: fieldDrawer.field.id, payload: basePayload })
        return
      }
      const payload: CreateFieldPayload = {
        table_id: detailQuery.data.id,
        name: values.name!,
        ...basePayload,
      }
      createFieldMutation.mutate(payload)
    })
  }

  return (
    <div className="page-grid">
      {holder}
      <section className="panel panel-pad">
        <div className="toolbar">
          <Typography.Title level={4} style={{ margin: 0 }}>元数据管理</Typography.Title>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateTable}>新建表</Button>
        </div>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input.Search
            value={search}
            placeholder="表名/字段/描述"
            allowClear
            onChange={(event) => setSearch(event.target.value)}
            onSearch={(value) => {
              if (value) params.set('search', value)
              else params.delete('search')
              setParams(params)
            }}
          />
          <Select
            value={layer}
            onChange={(value) => {
              setLayer(value)
              if (value === 'ALL') params.delete('layer')
              else params.set('layer', value)
              setParams(params)
            }}
            options={layers.map((value) => ({ value, label: value === 'ALL' ? '全部层级' : value }))}
            style={{ width: '100%' }}
          />
        </Space>
        <div className="table-list" style={{ marginTop: 14 }}>
          {tableQuery.data?.map((table) => (
            <button
              type="button"
              className={`table-row ${selectedTable?.id === table.id ? 'selected' : ''}`}
              key={table.id}
              onClick={() => setSelected(table)}
            >
              <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text strong>{table.name}</Typography.Text>
                <Tag>{table.layer}</Tag>
              </Space>
              <Typography.Paragraph className="muted" ellipsis={{ rows: 2 }} style={{ margin: '6px 0 0' }}>
                {table.description || '无描述'} · {table.field_count} fields
              </Typography.Paragraph>
            </button>
          ))}
        </div>
      </section>

      <section className="panel panel-pad">
        {detailQuery.data ? (
          <>
            <div className="toolbar">
              <div>
                <Typography.Title level={3} style={{ margin: 0 }}>{detailQuery.data.name}</Typography.Title>
                <Typography.Text className="muted">{detailQuery.data.description}</Typography.Text>
              </div>
              <Space wrap>
                <Button icon={<EditOutlined />} onClick={openEditTable}>编辑表</Button>
                <Button icon={<PlusOutlined />} onClick={() => {
                  fieldForm.resetFields()
                  fieldForm.setFieldsValue({ field_type: 'STRING', is_nullable: true, is_partition: false, description: '' })
                  setFieldDrawer({ mode: 'create' })
                }}>新建字段</Button>
                <Button icon={<EyeOutlined />} onClick={() => setYamlTable(detailQuery.data.name)}>预览 YAML</Button>
                <Link to={`/metadata/lineage?table=${detailQuery.data.name}`}>
                  <Button icon={<ForkOutlined />}>查看血缘</Button>
                </Link>
                <Link to={`/schema-evolution?table=${detailQuery.data.name}`}>
                  <Button icon={<HistoryOutlined />}>演化历史</Button>
                </Link>
                <Popconfirm title="删除表" description="会先检查字段下游依赖。" onConfirm={() => deleteTableMutation.mutate(detailQuery.data.id)}>
                  <Button danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
              </Space>
            </div>
            <Descriptions bordered size="small" column={4}>
              <Descriptions.Item label="层级">{detailQuery.data.layer}</Descriptions.Item>
              <Descriptions.Item label="优先级">{detailQuery.data.layer_priority}</Descriptions.Item>
              <Descriptions.Item label="存储">{detailQuery.data.storage_type}</Descriptions.Item>
              <Descriptions.Item label="字段数">{detailQuery.data.fields.length}</Descriptions.Item>
            </Descriptions>
            <Table
              style={{ marginTop: 16 }}
              rowKey="id"
              size="small"
              columns={columns}
              dataSource={detailQuery.data.fields}
              pagination={false}
            />
          </>
        ) : (
          <Typography.Text className="muted">请选择一张表</Typography.Text>
        )}
      </section>

      <Modal
        title={tableModal === 'edit' ? '编辑表' : '新建表'}
        open={Boolean(tableModal)}
        onCancel={() => setTableModal(undefined)}
        width={760}
        footer={[
          <Button key="cancel" onClick={() => setTableModal(undefined)}>取消</Button>,
          tableModal === 'create' ? (
            <Button key="save-export" icon={<SaveOutlined />} onClick={() => submitTable(true)} loading={schemaApplyMutation.isPending}>
              保存并导出 YAML
            </Button>
          ) : null,
          <Button key="save" type="primary" onClick={() => submitTable(false)} loading={createTableMutation.isPending || updateTableMutation.isPending}>
            保存
          </Button>,
        ]}
      >
        <Form layout="vertical" form={tableForm}>
          <Form.Item name="name" label="表名" rules={[{ required: true }]}><Input disabled={tableModal === 'edit'} /></Form.Item>
          <Space style={{ width: '100%' }} align="start">
            <Form.Item name="layer" label="层级" rules={[{ required: true }]}><Select options={layers.filter((item) => item !== 'ALL').map((value) => ({ value, label: value }))} style={{ width: 180 }} /></Form.Item>
            <Form.Item name="storage_type" label="存储" rules={[{ required: true }]}><Select options={storageTypes.map((value) => ({ value, label: value }))} style={{ width: 180 }} /></Form.Item>
          </Space>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
          {tableModal === 'create' ? (
            <Form.List name="fields">
              {(fields, { add, remove }) => (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Typography.Text strong>初始字段</Typography.Text>
                  {fields.map((field) => (
                    <Space key={field.key} align="baseline" wrap>
                      <Form.Item name={[field.name, 'name']} rules={[{ required: true, message: '字段名必填' }]}><Input placeholder="字段名" /></Form.Item>
                      <Form.Item name={[field.name, 'data_type']}><Select options={fieldTypes.map((value) => ({ value, label: value }))} style={{ width: 130 }} /></Form.Item>
                      <Form.Item name={[field.name, 'nullable']} valuePropName="checked"><Checkbox>可空</Checkbox></Form.Item>
                      <Form.Item name={[field.name, 'partition']} valuePropName="checked"><Checkbox>分区</Checkbox></Form.Item>
                      <Form.Item name={[field.name, 'description']}><Input placeholder="描述" /></Form.Item>
                      <Button danger icon={<DeleteOutlined />} onClick={() => remove(field.name)} />
                    </Space>
                  ))}
                  <Button icon={<PlusOutlined />} onClick={() => add({ data_type: 'STRING', nullable: true, partition: false })}>添加字段</Button>
                </Space>
              )}
            </Form.List>
          ) : null}
        </Form>
      </Modal>

      <Drawer
        title={fieldDrawer?.mode === 'edit' ? '编辑字段' : '新建字段'}
        open={Boolean(fieldDrawer)}
        onClose={() => setFieldDrawer(undefined)}
        width={560}
        extra={<Button type="primary" onClick={submitField} loading={createFieldMutation.isPending || updateFieldMutation.isPending}>保存</Button>}
      >
        <Form layout="vertical" form={fieldForm}>
          {fieldDrawer?.mode === 'create' ? <Form.Item name="name" label="字段名" rules={[{ required: true }]}><Input /></Form.Item> : null}
          <Form.Item name="field_type" label="类型" rules={[{ required: true }]}><Select options={fieldTypes.map((value) => ({ value, label: value }))} /></Form.Item>
          <Space>
            <Form.Item name="is_nullable" valuePropName="checked"><Checkbox>可空</Checkbox></Form.Item>
            <Form.Item name="is_partition" valuePropName="checked"><Checkbox>分区字段</Checkbox></Form.Item>
          </Space>
          <Form.Item name="expression" label="表达式"><Input.TextArea rows={4} /></Form.Item>
          <Form.Item name="upstream_text" label="上游字段"><Input.TextArea rows={3} placeholder="每行一个: table.field" /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Drawer>

      <Drawer title={`${yamlTable ?? ''} YAML`} open={Boolean(yamlTable)} onClose={() => setYamlTable(undefined)} width={720}>
        <pre>{yamlQuery.data?.content ?? 'loading...'}</pre>
      </Drawer>
    </div>
  )
}
