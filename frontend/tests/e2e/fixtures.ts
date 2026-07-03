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

export const lineageGraph = {
  root_table: 'dws_cell_hourly',
  depth: 2,
  include_upstream: true,
  include_downstream: true,
  graph_version: 'v-e2e',
  saved_sql: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q',
  tables: [
    {
      ...tables[0],
      fields: tableDetail.fields,
      sql_logic: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q',
      sql_dialect: 'spark_hive',
      sql_source: 'generated',
      sql_updated_at: '2026-07-03T10:00:00Z',
    },
    {
      ...tables[1],
      fields: tableDetail.fields,
      sql_logic: null,
      sql_dialect: null,
      sql_source: null,
      sql_updated_at: '',
    },
  ],
  table_edges: [
    {
      source: 'dwd_session_qos',
      target: 'dws_cell_hourly',
      direction: 'upstream',
      field_edge_count: 1,
      calc_type_counts: { AGGREGATE: 1 },
      fields: ['avg_rsrp'],
    },
  ],
  field_edges: [
    {
      edge_id: 'edge-1',
      from_table: 'dwd_session_qos',
      from_field: 'avg_rsrp',
      to_table: 'dws_cell_hourly',
      to_field: 'avg_rsrp',
      transform_expr: 'AVG(q.avg_rsrp)',
      calc_type: 'AGGREGATE',
      calc_params: { function: 'AVG', group_by: ['cell_id'] },
      created_at: '2026-07-03T10:00:00Z',
      updated_at: '2026-07-03T10:00:00Z',
    },
  ],
}

export const lineageSqlPreview = {
  table: 'dws_cell_hourly',
  sql: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q GROUP BY cell_id',
  complete: true,
  warnings: [],
  saved_sql: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q',
  changed: true,
}

export const lineageSqlImportPreview = {
  table: 'dws_cell_hourly',
  sql: 'SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q GROUP BY cell_id',
  fields: [
    {
      action: 'update',
      field: 'avg_rsrp',
      expression: 'AVG(q.avg_rsrp)',
      field_type: 'DOUBLE',
      upstream: [{ table: 'dwd_session_qos', field: 'avg_rsrp' }],
    },
  ],
  edges: [{ action: 'update', edge: lineageGraph.field_edges[0] }],
  warnings: [],
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
  await page.route('**/api/lineage/graph**', (route) => json(route, lineageGraph))
  await page.route('**/api/lineage/sql/preview', (route) => json(route, lineageSqlPreview))
  await page.route('**/api/lineage/sql/import/preview', (route) => json(route, lineageSqlImportPreview))
  await page.route('**/api/lineage/sql/apply', (route) => json(route, lineageSqlPreview))
}
