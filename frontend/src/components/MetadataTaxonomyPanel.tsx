import { SettingOutlined } from '@ant-design/icons'
import { Button, Checkbox, Input, Radio, Select, Space, Tree, Typography } from 'antd'
import type { DataNode } from 'antd/es/tree'
import { useMemo } from 'react'
import type { CategoryNode, TagGroup } from '../api/client'

type MetadataTaxonomyPanelProps = {
  categories?: CategoryNode[]
  tagGroups?: TagGroup[]
  selectedCategoryId?: string
  includeChildren: boolean
  selectedTagIds: string[]
  tagMatch: 'any' | 'all'
  layer: string
  search: string
  layers: string[]
  onSearchChange: (value: string) => void
  onSearchSubmit: (value: string) => void
  onLayerChange: (value: string) => void
  onCategoryChange: (value?: string) => void
  onIncludeChildrenChange: (value: boolean) => void
  onTagsChange: (value: string[]) => void
  onTagMatchChange: (value: 'any' | 'all') => void
  onOpenManager: () => void
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

function treeNodes(categories: CategoryNode[]): DataNode[] {
  return categories.map((category) => ({
    key: category.id,
    title: `${taxonomyLabel(category)} (${category.table_count})`,
    children: treeNodes(category.children),
  }))
}

function categoryIds(categories: CategoryNode[]): string[] {
  return categories.flatMap((category) => [category.id, ...categoryIds(category.children)])
}

export default function MetadataTaxonomyPanel({
  categories = [],
  tagGroups = [],
  selectedCategoryId,
  includeChildren,
  selectedTagIds,
  tagMatch,
  layer,
  search,
  layers,
  onSearchChange,
  onSearchSubmit,
  onLayerChange,
  onCategoryChange,
  onIncludeChildrenChange,
  onTagsChange,
  onTagMatchChange,
  onOpenManager,
}: MetadataTaxonomyPanelProps) {
  const categoryTree = useMemo(() => treeNodes(categories), [categories])
  const expandedCategoryIds = useMemo(() => categoryIds(categories), [categories])
  const tagOptions = useMemo(
    () =>
      tagGroups.flatMap((group) =>
        group.tags.map((tag) => ({
          value: tag.id,
          label: `${taxonomyLabel(tag)} · ${taxonomyLabel(group)}`,
        })),
      ),
    [tagGroups],
  )

  return (
    <Space direction="vertical" size={14} style={{ width: '100%' }}>
      <div className="metadata-taxonomy-header">
        <Typography.Title level={4} style={{ margin: 0 }}>
          元数据管理
        </Typography.Title>
        <Button icon={<SettingOutlined />} onClick={onOpenManager}>
          管理分类
        </Button>
      </div>

      <Input.Search
        value={search}
        placeholder="表名/字段/描述"
        allowClear
        onChange={(event) => onSearchChange(event.target.value)}
        onSearch={onSearchSubmit}
      />

      <Select
        value={layer}
        onChange={onLayerChange}
        options={layers.map((value) => ({ value, label: value === 'ALL' ? '全部层级' : value }))}
        style={{ width: '100%' }}
      />

      <div className="metadata-filter-block">
        <div className="metadata-filter-block-title">
          <Typography.Text strong>主分类</Typography.Text>
          <Checkbox checked={includeChildren} onChange={(event) => onIncludeChildrenChange(event.target.checked)}>
            包含子类
          </Checkbox>
        </div>
        <Button type="link" size="small" className="metadata-taxonomy-all" onClick={() => onCategoryChange(undefined)}>
          全部
        </Button>
        <Tree
          blockNode
          selectedKeys={selectedCategoryId ? [selectedCategoryId] : []}
          expandedKeys={expandedCategoryIds}
          treeData={categoryTree}
          onSelect={(keys) => onCategoryChange(typeof keys[0] === 'string' ? keys[0] : undefined)}
        />
      </div>

      <div className="metadata-filter-block">
        <div className="metadata-filter-block-title">
          <Typography.Text strong>标签</Typography.Text>
          <Radio.Group
            size="small"
            value={tagMatch}
            onChange={(event) => onTagMatchChange(event.target.value as 'any' | 'all')}
            optionType="button"
            buttonStyle="solid"
          >
            <Radio.Button value="any">任一</Radio.Button>
            <Radio.Button value="all">全部</Radio.Button>
          </Radio.Group>
        </div>
        <Select
          mode="multiple"
          allowClear
          value={selectedTagIds}
          options={tagOptions}
          onChange={onTagsChange}
          placeholder="选择标签"
          style={{ width: '100%' }}
        />
      </div>
    </Space>
  )
}
