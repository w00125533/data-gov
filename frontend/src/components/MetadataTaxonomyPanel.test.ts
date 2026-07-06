import { describe, expect, it } from 'vitest'
import type { CategoryNode, TableSummary } from '../api/client'
import { buildCategoryTreeNodes } from './metadataTaxonomyTree'

const categories: CategoryNode[] = [
  {
    id: 'category:network',
    code: 'network',
    name: '网络',
    level: 1,
    sort_order: 1,
    protected: true,
    active: true,
    table_count: 1,
    children: [
      {
        id: 'category:network.quality',
        code: 'network.quality',
        name: '质量',
        level: 2,
        sort_order: 1,
        protected: false,
        active: true,
        table_count: 1,
        children: [],
      },
    ],
  },
]

const tables: TableSummary[] = [
  {
    id: 'table-1',
    name: 'dwd_session_qos',
    layer: 'DWD',
    layer_priority: 2,
    storage_type: 'HIVE',
    description: '会话级 QoS 明细',
    field_count: 9,
    category: {
      id: 'category:network.quality',
      code: 'network.quality',
      name: '质量',
      path: ['网络', '质量'],
      active: true,
    },
    tags: [],
  },
]

describe('buildCategoryTreeNodes', () => {
  it('attaches tables under their level-2 category nodes', () => {
    const tree = buildCategoryTreeNodes(categories, tables)
    const quality = tree[0].children?.[0]
    const table = quality?.children?.[0]

    expect(quality?.key).toBe('category:network.quality')
    expect(table?.key).toBe('table:table-1')
    expect(table?.title).toBe('dwd_session_qos · DWD')
    expect(table?.isLeaf).toBe(true)
  })
})
