import { PlusOutlined, SettingOutlined } from '@ant-design/icons'
import { Button, Input, Select, Space, Tree, Typography } from 'antd'
import { useMemo, useState } from 'react'
import type { CategoryNode, TableSummary, TagGroup } from '../api/client'
import { buildCategoryTreeNodes, taxonomyLabel } from './metadataTaxonomyTree'

type MetadataTaxonomyPanelProps = {
  categories?: CategoryNode[]
  tables?: TableSummary[]
  tagGroups?: TagGroup[]
  selectedCategoryId?: string
  selectedTableId?: string
  selectedTagIds: string[]
  search: string
  onSearchChange: (value: string) => void
  onSearchSubmit: (value: string) => void
  onCategoryChange: (value?: string) => void
  onTableSelect: (table: TableSummary) => void
  onTagsChange: (value: string[]) => void
  onCreateTable: () => void
  onOpenManager: () => void
}

function expandableCategoryIds(categories: CategoryNode[]): Set<string> {
  return categories.reduce((ids, category) => {
    if (category.children.length > 0) {
      ids.add(category.id)
      expandableCategoryIds(category.children).forEach((id) => ids.add(id))
    }
    return ids
  }, new Set<string>())
}

export default function MetadataTaxonomyPanel({
  categories = [],
  tables = [],
  tagGroups = [],
  selectedCategoryId,
  selectedTableId,
  selectedTagIds,
  search,
  onSearchChange,
  onSearchSubmit,
  onCategoryChange,
  onTableSelect,
  onTagsChange,
  onCreateTable,
  onOpenManager,
}: MetadataTaxonomyPanelProps) {
  const [expandedCategoryIds, setExpandedCategoryIds] = useState<string[]>([])
  const categoryTree = useMemo(() => buildCategoryTreeNodes(categories, tables), [categories, tables])
  const expandableCategories = useMemo(() => expandableCategoryIds(categories), [categories])
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
  const tableByKey = useMemo(
    () => new Map(tables.map((table) => [`table:${table.id}`, table])),
    [tables],
  )

  return (
    <Space orientation="vertical" size={14} style={{ width: '100%' }}>
      <div className="metadata-taxonomy-header">
        <Typography.Title level={4} style={{ margin: 0 }}>
          元数据管理
        </Typography.Title>
      </div>

      <Input.Search
        value={search}
        placeholder="表名/字段/描述"
        allowClear
        onChange={(event) => onSearchChange(event.target.value)}
        onSearch={onSearchSubmit}
      />

      <div className="metadata-filter-block">
        <Space className="metadata-taxonomy-actions" size={8} wrap>
          <Button type="link" size="small" className="metadata-taxonomy-all" onClick={() => onCategoryChange(undefined)}>
            全部
          </Button>
          <Button size="small" icon={<PlusOutlined />} onClick={onCreateTable}>
            新建表
          </Button>
          <Button size="small" icon={<SettingOutlined />} onClick={onOpenManager}>
            管理分类
          </Button>
        </Space>
        <Tree
          blockNode
          selectedKeys={selectedCategoryId ? [selectedCategoryId] : selectedTableId ? [`table:${selectedTableId}`] : []}
          expandedKeys={expandedCategoryIds}
          onExpand={(keys, info) => {
            setExpandedCategoryIds(keys.map(String))
            const key = String(info.node.key)
            if (!tableByKey.has(key)) {
              onCategoryChange(key)
            }
          }}
          treeData={categoryTree}
          onSelect={(keys) => {
            const key = typeof keys[0] === 'string' ? keys[0] : undefined
            if (!key) return
            const table = tableByKey.get(key)
            if (table) {
              onTableSelect(table)
              return
            }
            if (expandableCategories.has(key) && !expandedCategoryIds.includes(key)) {
              setExpandedCategoryIds((currentKeys) => [...currentKeys, key])
            }
            onCategoryChange(key)
          }}
        />
      </div>

      <div className="metadata-filter-block">
        <div className="metadata-filter-block-title">
          <Typography.Text strong>标签</Typography.Text>
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
