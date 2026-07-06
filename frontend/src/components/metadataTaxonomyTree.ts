import type { DataNode } from 'antd/es/tree'
import type { CategoryNode, TableSummary } from '../api/client'

const taxonomyLabels: Record<string, string> = {
  network: '网络',
  'network.coverage': '覆盖',
  'network.quality': '质量',
  'source-data': '源数据',
  'source-data.chr': 'CHR',
  'network-domain': '网络域',
}

export function taxonomyLabel(item: { code: string; name: string }) {
  return taxonomyLabels[item.code] ?? item.name
}

function tablesByCategory(tables: TableSummary[]) {
  return tables.reduce((grouped, table) => {
    const categoryId = table.category?.id
    if (!categoryId) return grouped
    const categoryTables = grouped.get(categoryId) ?? []
    categoryTables.push(table)
    grouped.set(categoryId, categoryTables)
    return grouped
  }, new Map<string, TableSummary[]>())
}

function tableTreeNode(table: TableSummary): DataNode {
  return {
    key: `table:${table.id}`,
    title: `${table.name} · ${table.layer}`,
    isLeaf: true,
    className: 'metadata-taxonomy-table-node',
  }
}

export function buildCategoryTreeNodes(categories: CategoryNode[], tables: TableSummary[]): DataNode[] {
  const groupedTables = tablesByCategory(tables)
  return categories.map((category) => ({
    key: category.id,
    title: `${taxonomyLabel(category)} (${category.table_count})`,
    children: [
      ...buildCategoryTreeNodes(category.children, tables),
      ...(groupedTables.get(category.id) ?? []).map(tableTreeNode),
    ],
  }))
}
