import {
  DeleteOutlined,
  EditOutlined,
  ExportOutlined,
  EyeOutlined,
  ForkOutlined,
  HistoryOutlined,
  PlusOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import Editor from '@monaco-editor/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Button,
  Checkbox,
  Descriptions,
  Drawer,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  api,
  type CategoryRef,
  type CreateFieldPayload,
  type CreateTablePayload,
  type FieldResponse,
  type Layer,
  type TableResponse,
  type TableSummary,
  type TagRef,
  type UpdateFieldPayload,
  type UpstreamRef,
} from '../api/client'
import FieldUpstreamEditor from '../components/FieldUpstreamEditor'
import MetadataTaxonomyPanel from '../components/MetadataTaxonomyPanel'

const layers: Array<Layer | 'ALL'> = ['ALL', 'ODS', 'DWD', 'DWS', 'ADS', 'EVAL']
const fieldTypes = ['STRING', 'INT', 'BIGINT', 'DOUBLE', 'TIMESTAMP', 'DATE']
const storageTypes = ['KAFKA', 'HIVE', 'STARROCKS']

const taxonomyLabels: Record<string, string> = {
  network: '网络',
  'network.coverage': '覆盖',
  'network.quality': '质量',
  'source-data': '源数据',
  'source-data.chr': 'CHR',
}

function taxonomyLabel(item: { code: string; name: string }) {
  return taxonomyLabels[item.code] ?? item.name
}

function categoryPathLabel(category?: CategoryRef | null) {
  if (!category) return '未归类'
  return category.path.map((part, index) => {
    if (index === 0 && part === 'Network') return '网络'
    if (index === 0 && part === 'Source Data') return '源数据'
    const codePart = category.code.split('.')[index]
    const codePrefix = category.code.split('.').slice(0, index + 1).join('.')
    return taxonomyLabels[codePrefix] ?? taxonomyLabels[codePart] ?? part
  }).join(' / ')
}

function tagLabel(tag: TagRef) {
  return taxonomyLabel(tag)
}

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
  upstream?: UpstreamRef[]
}

export default function Metadata() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [apiMessage, holder] = message.useMessage()
  const [layer, setLayer] = useState<string>(params.get('layer') ?? 'ALL')
  const [search, setSearch] = useState(params.get('search') ?? '')
  const [categoryId, setCategoryId] = useState<string | undefined>(params.get('category_id') ?? undefined)
  const [includeChildren, setIncludeChildren] = useState(params.get('include_children') !== 'false')
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>(params.getAll('tag_ids'))
  const [tagMatch, setTagMatch] = useState<'any' | 'all'>(params.get('tag_match') === 'all' ? 'all' : 'any')
  const [taxonomyDrawerOpen, setTaxonomyDrawerOpen] = useState(false)
  const [selected, setSelected] = useState<TableSummary | undefined>()
  const [yamlTable, setYamlTable] = useState<string | undefined>()
  const [tableModal, setTableModal] = useState<'create' | 'edit' | undefined>()
  const [fieldDrawer, setFieldDrawer] = useState<{ mode: 'create' | 'edit'; field?: FieldResponse } | undefined>()
  const [tableForm] = Form.useForm<TableFormValues>()
  const [fieldForm] = Form.useForm<FieldFormValues>()
  const expressionValue = Form.useWatch('expression', fieldForm)

  const categoriesQuery = useQuery({
    queryKey: ['metadata-categories-tree'],
    queryFn: api.categoriesTree,
  })

  const tagsQuery = useQuery({
    queryKey: ['metadata-tags'],
    queryFn: api.tags,
  })

  const tableQuery = useQuery({
    queryKey: ['tables', layer, search, categoryId, includeChildren, selectedTagIds, tagMatch],
    queryFn: () => api.tables({
      layer: layer === 'ALL' ? undefined : layer,
      search,
      category_id: categoryId,
      include_children: categoryId ? includeChildren : undefined,
      tag_ids: selectedTagIds.length ? selectedTagIds : undefined,
      tag_match: selectedTagIds.length ? tagMatch : undefined,
    }),
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

  function updateUrl(updates: Record<string, string | string[] | boolean | undefined>) {
    const nextParams = new URLSearchParams(params)
    Object.entries(updates).forEach(([key, value]) => {
      nextParams.delete(key)
      if (Array.isArray(value)) {
        value.forEach((item) => {
          if (item) nextParams.append(key, item)
        })
        return
      }
      if (value !== undefined && value !== '') {
        nextParams.set(key, String(value))
      }
    })
    setParams(nextParams)
  }

  function resetSelectedTable() {
    setSelected(undefined)
  }

  function handleSearchSubmit(value: string) {
    updateUrl({ search: value || undefined })
  }

  function handleLayerChange(value: string) {
    setLayer(value)
    resetSelectedTable()
    updateUrl({ layer: value === 'ALL' ? undefined : value })
  }

  function handleCategoryChange(value?: string) {
    setCategoryId(value)
    resetSelectedTable()
    updateUrl({ category_id: value })
  }

  function handleIncludeChildrenChange(value: boolean) {
    setIncludeChildren(value)
    resetSelectedTable()
    updateUrl({ include_children: value ? undefined : 'false' })
  }

  function handleTagsChange(value: string[]) {
    setSelectedTagIds(value)
    resetSelectedTable()
    updateUrl({ tag_ids: value })
  }

  function handleTagMatchChange(value: 'any' | 'all') {
    setTagMatch(value)
    resetSelectedTable()
    updateUrl({ tag_match: value === 'any' ? undefined : value })
  }

  const createTableMutation = useMutation({
    mutationFn: async (values: TableFormValues) => {
      const table = await api.createTable({
        name: values.name,
        layer: values.layer,
        storage_type: values.storage_type,
        description: values.description,
      })
      const initialFields = (values.fields ?? []).filter((field) => field.name)
      for (const field of initialFields) {
        await api.createField({
          table_id: table.id,
          name: field.name!,
          field_type: field.data_type ?? 'STRING',
          is_nullable: field.nullable ?? true,
          is_partition: field.partition ?? false,
          expression: field.expression || null,
          description: field.description ?? '',
          upstream: [],
        })
      }
      return api.table(table.id)
    },
    onSuccess: (table) => {
      apiMessage.success('表已创建')
      setTableModal(undefined)
      tableForm.resetFields()
      refreshMetadata(table)
    },
    onError: (error) => apiMessage.error(`创建失败: ${(error as Error).message}`),
  })

  const updateTableMutation = useMutation({
    mutationFn: (values: TableFormValues) => api.updateTable(detailQuery.data!.id, {
      layer: values.layer,
      storage_type: values.storage_type,
      description: values.description,
    }),
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

  const yamlExportMutation = useMutation({
    mutationFn: (table?: string) => api.yamlExport(table),
    onSuccess: (payload) => {
      apiMessage.success(`已导出 ${payload.files.length} 个 YAML 文件`)
    },
    onError: (error) => apiMessage.error(`导出失败: ${(error as Error).message}`),
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

  const columns: ColumnsType<FieldResponse> = [
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
                  upstream: row.upstream,
                })
                setFieldDrawer({ mode: 'edit', field: row })
              }}
            />
            <Button size="small" danger icon={<DeleteOutlined />} onClick={() => void confirmDeleteField(row)} />
          </Space>
        ),
      },
    ]

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
      createTableMutation.mutate(values)
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
        upstream: values.upstream ?? [],
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

  async function confirmDeleteField(field: FieldResponse) {
    if (!detailQuery.data) return
    try {
      const impact = await api.impact({ table: detailQuery.data.name, field: field.name })
      if (impact.has_downstream) {
        Modal.warning({
          title: '字段存在下游依赖',
          content: `影响下游: ${impact.downstream.map((edge) => `${edge.to_table}.${edge.to_field}`).join(', ')}`,
        })
        return
      }
      deleteFieldMutation.mutate(field.id)
    } catch (error) {
      apiMessage.error(`影响检查失败: ${(error as Error).message}`)
    }
  }

  async function confirmDeleteTable(table: TableResponse) {
    try {
      const impact = await api.impact({ table: table.name })
      if (impact.has_downstream) {
        Modal.warning({
          title: '表存在下游依赖',
          content: `影响下游表: ${impact.affected_tables.join(', ')}`,
        })
        return
      }
      deleteTableMutation.mutate(table.id)
    } catch (error) {
      apiMessage.error(`影响检查失败: ${(error as Error).message}`)
    }
  }

  function openCreateDownstreamTable() {
    if (!detailQuery.data) return
    tableForm.resetFields()
    tableForm.setFieldsValue({
      name: `${detailQuery.data.name}_downstream`,
      layer: detailQuery.data.layer,
      storage_type: detailQuery.data.storage_type as CreateTablePayload['storage_type'],
      description: `下游表，来源: ${detailQuery.data.name}`,
      fields: [{ data_type: 'STRING', nullable: true, partition: false, description: `来自 ${detailQuery.data.name}` }],
    })
    setTableModal('create')
  }

  return (
    <div className="page-grid">
      {holder}
      <section className="panel panel-pad">
        <MetadataTaxonomyPanel
          categories={categoriesQuery.data}
          tagGroups={tagsQuery.data}
          selectedCategoryId={categoryId}
          includeChildren={includeChildren}
          selectedTagIds={selectedTagIds}
          tagMatch={tagMatch}
          layer={layer}
          search={search}
          layers={layers}
          onSearchChange={setSearch}
          onSearchSubmit={handleSearchSubmit}
          onLayerChange={handleLayerChange}
          onCategoryChange={handleCategoryChange}
          onIncludeChildrenChange={handleIncludeChildrenChange}
          onTagsChange={handleTagsChange}
          onTagMatchChange={handleTagMatchChange}
          onOpenManager={() => setTaxonomyDrawerOpen(true)}
        />
        <Space className="metadata-left-actions" wrap>
          <Button icon={<ExportOutlined />} onClick={() => yamlExportMutation.mutate(undefined)} loading={yamlExportMutation.isPending}>导出 YAML</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateTable}>新建表</Button>
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
              <Space size={[4, 4]} wrap style={{ marginTop: 8 }}>
                <Tag color={table.category ? 'blue' : 'default'}>{categoryPathLabel(table.category)}</Tag>
                {(table.tags ?? []).slice(0, 3).map((tag) => (
                  <Tag key={tag.id} color="geekblue">{tagLabel(tag)}</Tag>
                ))}
              </Space>
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
                  fieldForm.setFieldsValue({ field_type: 'STRING', is_nullable: true, is_partition: false, description: '', upstream: [] })
                  setFieldDrawer({ mode: 'create' })
                }}>新建字段</Button>
                <Button icon={<EyeOutlined />} onClick={() => setYamlTable(detailQuery.data.name)}>预览 YAML</Button>
                <Button icon={<ExportOutlined />} onClick={() => yamlExportMutation.mutate(detailQuery.data.name)} loading={yamlExportMutation.isPending}>导出单表</Button>
                <Link to={`/metadata/lineage?table=${detailQuery.data.name}`}>
                  <Button icon={<ForkOutlined />}>查看血缘</Button>
                </Link>
                <Link to={`/schema-evolution?table=${detailQuery.data.name}`}>
                  <Button icon={<HistoryOutlined />}>演化历史</Button>
                </Link>
                <Button icon={<PlusOutlined />} onClick={openCreateDownstreamTable}>创建下游表</Button>
                <Button danger icon={<DeleteOutlined />} onClick={() => void confirmDeleteTable(detailQuery.data)}>删除</Button>
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
        title="分类与标签管理"
        open={taxonomyDrawerOpen}
        onClose={() => setTaxonomyDrawerOpen(false)}
        width={520}
      >
        <Typography.Text className="muted">分类与标签管理将在后续任务中提供。</Typography.Text>
      </Drawer>

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
          <Form.Item label="表达式">
            <Editor
              height="180px"
              language="sql"
              value={expressionValue ?? ''}
              options={{ minimap: { enabled: false } }}
              onChange={(value) => fieldForm.setFieldValue('expression', value ?? '')}
            />
          </Form.Item>
          <Form.Item name="upstream" label="上游字段">
            <FieldUpstreamEditor />
          </Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Drawer>

      <Drawer title={`${yamlTable ?? ''} YAML`} open={Boolean(yamlTable)} onClose={() => setYamlTable(undefined)} width={720}>
        <pre>{yamlQuery.data?.content ?? 'loading...'}</pre>
      </Drawer>
    </div>
  )
}
