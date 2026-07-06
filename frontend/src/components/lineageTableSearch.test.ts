import { describe, expect, it } from 'vitest'
import type { TableSummary } from '../api/client'
import { buildLineageTableSelectOptions, selectedLineageTableCard, filterLineageTableOptions } from './lineageTableSearch'

const tables: TableSummary[] = [
  {
    id: '1',
    name: 'dws_cell_hourly',
    layer: 'DWS',
    layer_priority: 3,
    storage_type: 'HIVE',
    description: 'cell coverage summary',
    field_count: 8,
    category: { id: 'category:network.coverage', code: 'network.coverage', name: '覆盖', path: ['网络', '覆盖'], active: true },
    tags: [{ id: 'tag:network.coverage', code: 'network.coverage', name: '覆盖', active: true }],
  },
  {
    id: '2',
    name: 'eval_user_score',
    layer: 'EVAL',
    layer_priority: 5,
    storage_type: 'STARROCKS',
    description: 'daily qoe score',
    field_count: 6,
    category: { id: 'category:user.service', code: 'user.service', name: '业务信息', path: ['用户', '业务信息'], active: true },
    tags: [],
  },
]

describe('filterLineageTableOptions', () => {
  it('filters table candidates in real time by name, category, tag, and description', () => {
    expect(filterLineageTableOptions(tables, 'cell').map((table) => table.name)).toEqual(['dws_cell_hourly'])
    expect(filterLineageTableOptions(tables, '覆盖').map((table) => table.name)).toEqual(['dws_cell_hourly'])
    expect(filterLineageTableOptions(tables, 'qoe').map((table) => table.name)).toEqual(['eval_user_score'])
  })

  it('returns the first candidates when keyword is empty', () => {
    expect(filterLineageTableOptions(tables, '').map((table) => table.name)).toEqual(['dws_cell_hourly', 'eval_user_score'])
  })

  it('builds direct single-select options and the selected table card', () => {
    expect(buildLineageTableSelectOptions(tables)).toEqual([
      {
        value: 'dws_cell_hourly',
        label: 'dws_cell_hourly',
        searchText: 'dws_cell_hourly cell coverage summary DWS HIVE 网络 覆盖 覆盖',
        description: '网络 / 覆盖',
      },
      {
        value: 'eval_user_score',
        label: 'eval_user_score',
        searchText: 'eval_user_score daily qoe score EVAL STARROCKS 用户 业务信息',
        description: '用户 / 业务信息',
      },
    ])

    expect(selectedLineageTableCard(tables, 'eval_user_score')).toEqual({
      name: 'eval_user_score',
      description: '用户 / 业务信息',
    })
  })
})
