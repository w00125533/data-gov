import type { TableSummary } from '../api/client'

export type LineageTableSelectOption = {
  value: string
  label: string
  searchText: string
  description: string
}

function tableDescription(table: TableSummary) {
  return table.category?.path.join(' / ') || table.layer
}

function tableSearchText(table: TableSummary) {
  return [
    table.name,
    table.description,
    table.layer,
    table.storage_type,
    table.category?.path.join(' '),
    ...(table.tags ?? []).map((tag) => tag.name),
  ].filter(Boolean).join(' ')
}

export function filterLineageTableOptions(tables: TableSummary[] | undefined, keyword: string, limit = 8) {
  const normalizedKeyword = keyword.trim().toLowerCase()
  const source = tables ?? []
  if (!normalizedKeyword) return source.slice(0, limit)

  return source
    .filter((table) => {
      const haystack = [
        table.name,
        table.description,
        table.layer,
        table.storage_type,
        table.category?.path.join(' '),
        ...(table.tags ?? []).map((tag) => tag.name),
      ].join(' ').toLowerCase()
      return haystack.includes(normalizedKeyword)
    })
    .slice(0, limit)
}

export function buildLineageTableSelectOptions(tables: TableSummary[] | undefined): LineageTableSelectOption[] {
  return (tables ?? []).map((table) => ({
    value: table.name,
    label: table.name,
    searchText: tableSearchText(table),
    description: tableDescription(table),
  }))
}

export function selectedLineageTableCard(tables: TableSummary[] | undefined, tableName: string) {
  const table = (tables ?? []).find((item) => item.name === tableName)
  if (!table) return undefined
  return {
    name: table.name,
    description: tableDescription(table),
  }
}
