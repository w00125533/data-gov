import { expect, test } from '@playwright/test'
import { json, lineageGraph, lineageSqlPreview, mockCommonApis } from './fixtures'

test('lineage workspace renders expandable tables and direction filters', async ({ page }) => {
  await mockCommonApis(page)

  await page.goto('/metadata/lineage?table=dws_cell_hourly')

  await expect(page.getByRole('heading', { name: '血缘工作区' })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: '正向' })).toBeChecked()
  await expect(page.getByRole('checkbox', { name: '反向' })).toBeChecked()
  await expect(page.getByText('dws_cell_hourly').first()).toBeVisible()
  await expect(page.getByText('dwd_session_qos').first()).toBeVisible()

  await page.getByRole('button', { name: '展开 dws_cell_hourly' }).click()
  await expect(page.getByText('avg_rsrp').first()).toBeVisible()
  await expect(page.getByText('AVG(q.avg_rsrp)').first()).toBeVisible()

  await page.getByRole('checkbox', { name: '反向' }).uncheck()
  await expect(page.getByRole('button', { name: /dwd_session_qos\.avg_rsrp.*dws_cell_hourly\.avg_rsrp/ })).toBeHidden()
})

test('lineage workspace moves source endpoint onto a field anchor by drag', async ({ page }) => {
  let patchBody: unknown

  await mockCommonApis(page)
  await page.route('**/api/lineage/edges/edge-1/endpoints', async (route) => {
    patchBody = route.request().postDataJSON()
    await json(route, {
      ...lineageGraph.field_edges[0],
      ...(patchBody as Record<string, string>),
    })
  })
  await page.route('**/api/lineage/sql/preview', (route) => json(route, lineageSqlPreview))

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await page.getByRole('button', { name: '展开 dws_cell_hourly' }).click()
  await page.getByRole('button', { name: '展开 dwd_session_qos' }).click()

  await page.getByLabel('字段锚点 dwd_session_qos.hour_bucket').evaluate((target) => {
    const dataTransfer = new DataTransfer()
    dataTransfer.setData('application/lineage-edge-endpoint', '{malformed')
    target.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer }))
  })
  await expect.poll(() => patchBody).toBeUndefined()

  await page.getByRole('button', { name: '源锚点 edge-1' }).dragTo(page.getByRole('button', { name: '字段锚点 dwd_session_qos.hour_bucket' }))

  await expect.poll(() => patchBody).toEqual({
    from_table: 'dwd_session_qos',
    from_field: 'hour_bucket',
    to_table: 'dws_cell_hourly',
    to_field: 'avg_rsrp',
  })
})

test('lineage workspace moves source endpoint onto a field anchor by keyboard', async ({ page }) => {
  let patchBody: unknown

  await mockCommonApis(page)
  await page.route('**/api/lineage/edges/edge-1/endpoints', async (route) => {
    patchBody = route.request().postDataJSON()
    await json(route, {
      ...lineageGraph.field_edges[0],
      ...(patchBody as Record<string, string>),
    })
  })

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await page.getByRole('button', { name: '展开 dws_cell_hourly' }).click()
  await page.getByRole('button', { name: '展开 dwd_session_qos' }).click()

  await page.getByRole('button', { name: '源锚点 edge-1' }).press('Enter')
  await page.getByRole('button', { name: '字段锚点 dwd_session_qos.hour_bucket' }).press('Enter')

  await expect.poll(() => patchBody).toEqual({
    from_table: 'dwd_session_qos',
    from_field: 'hour_bucket',
    to_table: 'dws_cell_hourly',
    to_field: 'avg_rsrp',
  })
})

test('lineage workspace selects field edges from the keyboard', async ({ page }) => {
  await mockCommonApis(page)

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await page.getByRole('button', { name: /dwd_session_qos\.avg_rsrp.*dws_cell_hourly\.avg_rsrp/ }).focus()
  await page.keyboard.press('Enter')

  await expect(page.getByText('AVG(q.avg_rsrp)').last()).toBeVisible()
})

test('lineage workspace edits field edge config and previews generated sql', async ({ page }) => {
  let updateBody: unknown

  await mockCommonApis(page)
  await page.route('**/api/lineage/graph**', (route) => json(route, {
    ...lineageGraph,
    field_edges: [
      {
        ...lineageGraph.field_edges[0],
        calc_type: 'DIRECT',
      },
    ],
  }))
  await page.route('**/api/lineage/edges/edge-1', async (route) => {
    updateBody = route.request().postDataJSON()
    await json(route, {
      ...lineageGraph.field_edges[0],
      ...(updateBody as Record<string, unknown>),
    })
  })
  await page.route('**/api/lineage/sql/preview', (route) => json(route, lineageSqlPreview))

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await page.getByRole('button', { name: /dwd_session_qos\.avg_rsrp.*dws_cell_hourly\.avg_rsrp/ }).click()

  await expect(page.getByRole('heading', { name: '边计算配置' })).toBeVisible()
  await page.getByRole('combobox', { name: '计算类型' }).click()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await page.getByRole('button', { name: '保存边配置' }).click()

  await expect.poll(() => updateBody).toMatchObject({
    transform_expr: 'AVG(q.avg_rsrp)',
    calc_type: 'AGGREGATE',
    calc_params: { function: 'AVG', group_by: ['cell_id'] },
  })
  await expect(page.locator('pre.json-preview')).toContainText('SELECT AVG(q.avg_rsrp) AS avg_rsrp')
  await page.getByRole('button', { name: '同步到表定义' }).click()
  await expect(page.getByText('SQL 同步将在导入/应用流程中执行')).toBeVisible()
})
