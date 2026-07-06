import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, Drawer, Form, Input, InputNumber, Select, Space, Switch, Tabs, Typography, message } from 'antd'
import { useEffect, useMemo } from 'react'
import { api, type CategoryNode, type TagGroup } from '../api/client'

type MetadataTaxonomyDrawerProps = {
  open: boolean
  categories?: CategoryNode[]
  tagGroups?: TagGroup[]
  onClose: () => void
}

type CategoryFormValues = {
  parent_id: string
  name: string
  sort_order?: number
}

type TagGroupFormValues = {
  name: string
  sort_order?: number
}

type TagFormValues = {
  group_id: string
  name: string
  sort_order?: number
}

const taxonomyLabels: Record<string, string> = {
  network: '网络',
  'network.coverage': '覆盖',
  'network.quality': '质量',
  'source-data': '源数据',
  'source-data.chr': 'CHR',
  'network-domain': '网络域',
}

function taxonomyLabel(item: { code: string; name: string }) {
  return taxonomyLabels[item.code] ?? item.name
}

function slugify(value: string) {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
  return slug || `item-${Date.now()}`
}

export default function MetadataTaxonomyDrawer({
  open,
  categories = [],
  tagGroups = [],
  onClose,
}: MetadataTaxonomyDrawerProps) {
  const queryClient = useQueryClient()
  const [apiMessage, holder] = message.useMessage()
  const [categoryForm] = Form.useForm<CategoryFormValues>()
  const [tagGroupForm] = Form.useForm<TagGroupFormValues>()
  const [tagForm] = Form.useForm<TagFormValues>()

  const rootOptions = useMemo(
    () => categories.map((category) => ({ value: category.id, label: taxonomyLabel(category), code: category.code })),
    [categories],
  )

  const groupOptions = useMemo(
    () => tagGroups.map((group) => ({ value: group.id, label: taxonomyLabel(group), code: group.code })),
    [tagGroups],
  )

  useEffect(() => {
    if (!open) return
    if (!categoryForm.getFieldValue('parent_id') && rootOptions[0]) {
      categoryForm.setFieldValue('parent_id', rootOptions[0].value)
    }
  }, [categoryForm, open, rootOptions])

  useEffect(() => {
    if (!open) return
    if (!tagForm.getFieldValue('group_id') && groupOptions[0]) {
      tagForm.setFieldValue('group_id', groupOptions[0].value)
    }
  }, [groupOptions, open, tagForm])

  function invalidateTaxonomy() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ['metadata-categories'] }),
      queryClient.invalidateQueries({ queryKey: ['metadata-categories-tree'] }),
      queryClient.invalidateQueries({ queryKey: ['metadata-tags'] }),
      queryClient.invalidateQueries({ queryKey: ['tables'] }),
    ])
  }

  const createCategoryMutation = useMutation({
    mutationFn: (values: CategoryFormValues) => {
      const parent = rootOptions.find((item) => item.value === values.parent_id)
      return api.createCategory({
        parent_id: values.parent_id,
        name: values.name,
        code: `${parent?.code ?? 'category'}.${slugify(values.name)}`,
        sort_order: values.sort_order,
        active: true,
      })
    },
    onSuccess: async () => {
      apiMessage.success('小分类已新增')
      categoryForm.resetFields()
      categoryForm.setFieldsValue({ parent_id: rootOptions[0]?.value, sort_order: 10 })
      await invalidateTaxonomy()
    },
    onError: (error) => apiMessage.error(`新增小分类失败: ${(error as Error).message}`),
  })

  const updateCategoryStatusMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => api.updateCategoryStatus(id, { active }),
    onSuccess: () => invalidateTaxonomy(),
    onError: (error) => apiMessage.error(`更新分类状态失败: ${(error as Error).message}`),
  })

  const createTagGroupMutation = useMutation({
    mutationFn: (values: TagGroupFormValues) =>
      api.createTagGroup({
        name: values.name,
        code: slugify(values.name),
        sort_order: values.sort_order,
        active: true,
      }),
    onSuccess: async () => {
      apiMessage.success('标签组已新增')
      tagGroupForm.resetFields()
      tagGroupForm.setFieldsValue({ sort_order: 10 })
      await invalidateTaxonomy()
    },
    onError: (error) => apiMessage.error(`新增标签组失败: ${(error as Error).message}`),
  })

  const createTagMutation = useMutation({
    mutationFn: (values: TagFormValues) => {
      const group = groupOptions.find((item) => item.value === values.group_id)
      return api.createTag({
        group_id: values.group_id,
        name: values.name,
        code: `${group?.code ?? 'tag'}.${slugify(values.name)}`,
        sort_order: values.sort_order,
        active: true,
      })
    },
    onSuccess: async () => {
      apiMessage.success('标签已新增')
      tagForm.resetFields()
      tagForm.setFieldsValue({ group_id: groupOptions[0]?.value, sort_order: 10 })
      await invalidateTaxonomy()
    },
    onError: (error) => apiMessage.error(`新增标签失败: ${(error as Error).message}`),
  })

  const updateTagStatusMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => api.updateTagStatus(id, { active }),
    onSuccess: () => invalidateTaxonomy(),
    onError: (error) => apiMessage.error(`更新标签状态失败: ${(error as Error).message}`),
  })

  const updateTagGroupStatusMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.updateTagGroup(id, { active }),
    onSuccess: () => invalidateTaxonomy(),
    onError: (error) => apiMessage.error(`更新标签组状态失败: ${(error as Error).message}`),
  })

  return (
    <Drawer
      title="分类与标签管理"
      open={open}
      onClose={onClose}
      width={640}
      extra={<Button onClick={onClose}>关闭</Button>}
    >
      {holder}
      <Tabs
        items={[
          {
            key: 'categories',
            label: '分类',
            forceRender: true,
            children: (
              <Space orientation="vertical" size={16} style={{ width: '100%' }}>
                <Space orientation="vertical" size={10} style={{ width: '100%' }}>
                  {categories.map((root) => (
                    <div key={root.id}>
                      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Typography.Text strong>{taxonomyLabel(root)}</Typography.Text>
                        <Switch
                          aria-label={`${taxonomyLabel(root)} 状态`}
                          checked={root.active}
                          checkedChildren="启用"
                          unCheckedChildren="停用"
                          onChange={(active) => updateCategoryStatusMutation.mutate({ id: root.id, active })}
                        />
                      </Space>
                      <Space orientation="vertical" size={6} style={{ width: '100%', marginTop: 8, paddingLeft: 16 }}>
                        {root.children.map((child) => (
                          <Space key={child.id} style={{ justifyContent: 'space-between', width: '100%' }}>
                            <span>{taxonomyLabel(child)}</span>
                            <Switch
                              aria-label={`${taxonomyLabel(child)} 状态`}
                              checked={child.active}
                              size="small"
                              checkedChildren="启用"
                              unCheckedChildren="停用"
                              onChange={(active) => updateCategoryStatusMutation.mutate({ id: child.id, active })}
                            />
                          </Space>
                        ))}
                      </Space>
                    </div>
                  ))}
                </Space>

                <Form
                  layout="vertical"
                  form={categoryForm}
                  initialValues={{ parent_id: rootOptions[0]?.value, sort_order: 10 }}
                  onFinish={(values) => createCategoryMutation.mutate(values)}
                >
                  <Typography.Text strong>新增小分类</Typography.Text>
                  <Space align="start" wrap style={{ marginTop: 10 }}>
                    <Form.Item name="parent_id" label="大分类" rules={[{ required: true }]}>
                      <Select options={rootOptions} style={{ width: 160 }} />
                    </Form.Item>
                    <Form.Item name="name" label="小分类" rules={[{ required: true, message: '请输入小分类' }]}>
                      <Input style={{ width: 180 }} />
                    </Form.Item>
                    <Form.Item name="sort_order" label="排序">
                      <InputNumber min={0} style={{ width: 110 }} />
                    </Form.Item>
                    <Form.Item label=" ">
                      <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        htmlType="submit"
                        loading={createCategoryMutation.isPending}
                      >
                        新增小分类
                      </Button>
                    </Form.Item>
                  </Space>
                </Form>
              </Space>
            ),
          },
          {
            key: 'tags',
            label: '标签',
            forceRender: true,
            children: (
              <Space orientation="vertical" size={16} style={{ width: '100%' }}>
                <Space orientation="vertical" size={10} style={{ width: '100%' }}>
                  {tagGroups.map((group) => (
                    <div key={group.id}>
                      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Typography.Text strong>{taxonomyLabel(group)}</Typography.Text>
                        <Switch
                          aria-label={`${taxonomyLabel(group)} 状态`}
                          checked={group.active}
                          checkedChildren="启用"
                          unCheckedChildren="停用"
                          onChange={(active) => updateTagGroupStatusMutation.mutate({ id: group.id, active })}
                        />
                      </Space>
                      <Space orientation="vertical" size={6} style={{ width: '100%', marginTop: 8, paddingLeft: 16 }}>
                        {group.tags.map((tag) => (
                          <Space key={tag.id} style={{ justifyContent: 'space-between', width: '100%' }}>
                            <span>{taxonomyLabel(tag)}</span>
                            <Switch
                              aria-label={`${taxonomyLabel(tag)} 状态`}
                              checked={tag.active}
                              size="small"
                              checkedChildren="启用"
                              unCheckedChildren="停用"
                              onChange={(active) => updateTagStatusMutation.mutate({ id: tag.id, active })}
                            />
                          </Space>
                        ))}
                      </Space>
                    </div>
                  ))}
                </Space>

                <Form
                  layout="vertical"
                  form={tagGroupForm}
                  initialValues={{ sort_order: 10 }}
                  onFinish={(values) => createTagGroupMutation.mutate(values)}
                >
                  <Typography.Text strong>新增标签组</Typography.Text>
                  <Space align="start" wrap style={{ marginTop: 10 }}>
                    <Form.Item name="name" label="标签组" rules={[{ required: true, message: '请输入标签组' }]}>
                      <Input style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item name="sort_order" label="排序">
                      <InputNumber min={0} style={{ width: 110 }} />
                    </Form.Item>
                    <Form.Item label=" ">
                      <Button type="primary" icon={<PlusOutlined />} htmlType="submit" loading={createTagGroupMutation.isPending}>
                        新增标签组
                      </Button>
                    </Form.Item>
                  </Space>
                </Form>

                <Form
                  layout="vertical"
                  form={tagForm}
                  initialValues={{ group_id: groupOptions[0]?.value, sort_order: 10 }}
                  onFinish={(values) => createTagMutation.mutate(values)}
                >
                  <Typography.Text strong>新增标签</Typography.Text>
                  <Space align="start" wrap style={{ marginTop: 10 }}>
                    <Form.Item name="group_id" label="标签组" rules={[{ required: true }]}>
                      <Select options={groupOptions} style={{ width: 160 }} />
                    </Form.Item>
                    <Form.Item name="name" label="标签" rules={[{ required: true, message: '请输入标签' }]}>
                      <Input style={{ width: 180 }} />
                    </Form.Item>
                    <Form.Item name="sort_order" label="排序">
                      <InputNumber min={0} style={{ width: 110 }} />
                    </Form.Item>
                    <Form.Item label=" ">
                      <Button type="primary" icon={<PlusOutlined />} htmlType="submit" loading={createTagMutation.isPending}>
                        新增标签
                      </Button>
                    </Form.Item>
                  </Space>
                </Form>
              </Space>
            ),
          },
        ]}
      />
    </Drawer>
  )
}
