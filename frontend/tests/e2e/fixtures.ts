import type { Page, Route } from '@playwright/test'

export const tables = [
  {
    id: 't1',
    name: 'dws_cell_hourly',
    layer: 'DWS',
    layer_priority: 3,
    storage_type: 'HIVE',
    description: '小区小时粒度汇总',
    field_count: 2,
  },
  {
    id: 't2',
    name: 'dwd_session_qos',
    layer: 'DWD',
    layer_priority: 2,
    storage_type: 'HIVE',
    description: '会话 QoS 明细',
    field_count: 2,
  },
]

export const tableDetail = {
  ...tables[0],
  fields: [
    {
      id: 'f1',
      name: 'avg_rsrp',
      field_type: 'DOUBLE',
      is_nullable: true,
      is_partition: false,
      expression: 'AVG(rsrp)',
      description: '平均 RSRP',
      version: 2,
      upstream: [{ table: 'dwd_session_qos', field: 'avg_rsrp' }],
    },
    {
      id: 'f2',
      name: 'hour_bucket',
      field_type: 'TIMESTAMP',
      is_nullable: false,
      is_partition: true,
      expression: "DATE_TRUNC('HOUR', timestamp)",
      description: '小时窗口',
      version: 1,
      upstream: [],
    },
  ],
}

export async function json(route: Route, body: unknown) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

export async function mockCommonApis(page: Page) {
  await page.route('**/api/tables?*', (route) => json(route, tables))
  await page.route('**/api/tables', (route) => json(route, tables))
  await page.route('**/api/tables/t1', (route) => json(route, tableDetail))
  await page.route('**/api/tables/t2', (route) => json(route, { ...tables[1], fields: tableDetail.fields }))
  await page.route('**/api/yaml/export**', (route) => json(route, { table: null, files: [{ table: 'dws_cell_hourly', path: 'metadata-yaml/L3-DWS/dws_cell_hourly.yaml', content: 'table_name: dws_cell_hourly' }] }))
  await page.route('**/api/yaml/preview/dws_cell_hourly', (route) => json(route, { table: 'dws_cell_hourly', path: 'metadata-yaml/L3-DWS/dws_cell_hourly.yaml', content: 'table_name: dws_cell_hourly' }))
  await page.route('**/api/metadata/impact**', (route) => json(route, { table: 'dws_cell_hourly', field: null, has_downstream: false, affected_tables: [], downstream: [] }))
}
