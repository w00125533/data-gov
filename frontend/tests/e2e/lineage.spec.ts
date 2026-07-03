import { expect, test, type Locator, type Page } from '@playwright/test'
import { json, lineageGraph, lineageSqlImportPreview, lineageSqlPreview, mockCommonApis } from './fixtures'

async function activateHiddenButton(page: Page, name: string | RegExp) {
  const button = page.getByRole('button').filter({ hasText: name })
  await button.focus()
  await page.keyboard.press('Enter')
}

function x6Canvas(page: Page) {
  return page.locator('.lineage-x6-canvas')
}

function x6FieldEdge(page: Page) {
  return page.locator('.lineage-x6-canvas .x6-graph [data-cell-id^="field-edge-"]').first()
}

function x6FieldEdgePath(page: Page) {
  return x6FieldEdge(page).locator('path').nth(1)
}

function x6MainHost(page: Page) {
  return page.locator('.lineage-x6-graph-host')
}

function x6TableToggle(page: Page, table: string) {
  return x6MainHost(page).locator(`g[data-cell-id="${table}"] rect[event="lineage:toggle-table"]`)
}

function x6Port(page: Page, table: string, port: string) {
  return x6MainHost(page).locator(`g[data-cell-id="${table}"] circle[port="${port}"]`)
}

function x6EdgeArrowhead(page: Page, type: 'source' | 'target') {
  return x6MainHost(page).locator(`g[data-cell-id="field-edge-s-edge-1"] .x6-edge-tool-${type}-arrowhead`)
}

async function locatorCenter(locator: Locator) {
  const box = await locator.boundingBox()
  expect(box).not.toBeNull()
  return {
    x: (box?.x ?? 0) + (box?.width ?? 0) / 2,
    y: (box?.y ?? 0) + (box?.height ?? 0) / 2,
  }
}

async function clickVisibleTableToggle(page: Page, table: string) {
  const toggle = x6TableToggle(page, table)
  await expect(toggle).toBeAttached()
  const point = await locatorCenter(toggle)
  await page.mouse.click(point.x, point.y)
}

async function dragVisibleSourceArrowheadToPort(page: Page, table: string, field: string) {
  const arrowhead = x6EdgeArrowhead(page, 'source')
  const port = x6Port(page, table, `out:${field}`)
  await expect(arrowhead).toBeAttached()
  await expect(port).toBeAttached()
  const start = await locatorCenter(arrowhead)
  const end = await locatorCenter(port)
  await page.mouse.move(start.x, start.y)
  await page.mouse.down()
  await page.mouse.move(end.x, end.y, { steps: 10 })
  await page.mouse.up()
}

async function clickRenderedX6Path(page: Page, pathLocator = x6FieldEdgePath(page)) {
  const point = await pathLocator.evaluate((path) => {
    const svgPath = path as SVGPathElement
    const middle = svgPath.getPointAtLength(svgPath.getTotalLength() / 2)
    const matrix = svgPath.getScreenCTM()
    if (!matrix) throw new Error('missing SVG screen transform')
    return {
      x: matrix.a * middle.x + matrix.c * middle.y + matrix.e,
      y: matrix.b * middle.x + matrix.d * middle.y + matrix.f,
    }
  })
  await page.mouse.click(point.x, point.y)
}

async function expectRenderedX6PathBounds(pathLocator: Locator) {
  const box = await pathLocator.boundingBox()
  expect(box).not.toBeNull()
  expect(box?.width ?? 0).toBeGreaterThan(0)
  expect(box?.height ?? -1).toBeGreaterThanOrEqual(0)
}

test('lineage workspace renders expandable tables and direction filters', async ({ page }) => {
  await mockCommonApis(page)

  await page.goto('/metadata/lineage?table=dws_cell_hourly')

  await expect(page.getByRole('heading', { name: '血缘工作区' })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: '前向' })).toBeChecked()
  await expect(page.getByRole('checkbox', { name: '后向' })).toBeChecked()
  await expect(page.locator('.lineage-x6-canvas .x6-graph')).toBeVisible()
  await expect(x6Canvas(page)).toContainText('dws_cell_hourly')
  await expect(x6Canvas(page)).toContainText('dwd_session_qos')
  await expect(page.locator('.lineage-x6-canvas .x6-graph [data-cell-id^="table-edge-"]').first()).toBeAttached()

  await clickVisibleTableToggle(page, 'dws_cell_hourly')
  await expect(x6Canvas(page)).toContainText('avg_rsrp')
  await expect(x6FieldEdge(page)).toBeAttached()

  await page.getByRole('checkbox', { name: '后向' }).uncheck()
  await expect(x6Canvas(page)).not.toContainText('dwd_session_qos')
})

test('lineage workspace previews imported select sql before applying', async ({ page }) => {
  let applyBody: unknown
  let graphCalls = 0
  let sqlPreviewCalls = 0
  await mockCommonApis(page)
  await page.route('**/api/lineage/graph**', (route) => {
    graphCalls += 1
    return json(route, {
      ...lineageGraph,
      graph_version: graphCalls === 1 ? 'v-e2e' : 'v-after-preview',
    })
  })
  await page.route('**/api/lineage/sql/preview', (route) => {
    sqlPreviewCalls += 1
    return json(route, lineageSqlPreview)
  })
  await page.route('**/api/lineage/sql/import/preview', (route) => json(route, lineageSqlImportPreview))
  await page.route('**/api/lineage/sql/apply', (route) => {
    applyBody = route.request().postDataJSON()
    return json(route, lineageSqlPreview)
  })

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await expect.poll(() => graphCalls).toBeGreaterThanOrEqual(1)
  const graphCallsBeforeDeliberateRefetch = graphCalls
  await page.getByRole('button', { name: '导入 SQL' }).click()
  await page.getByLabel('SQL 文本').fill('SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q GROUP BY cell_id')
  await page.getByRole('button', { name: '解析 SQL' }).click()
  await expect(page.getByText('字段变更')).toBeVisible()
  await expect(page.getByText(/update \| avg_rsrp \| AVG/)).toBeVisible()
  await page.getByRole('checkbox', { name: '后向' }).evaluate((checkbox) => {
    ;(checkbox as HTMLInputElement).click()
  })
  await expect.poll(() => graphCalls).toBeGreaterThan(graphCallsBeforeDeliberateRefetch)
  const graphCallsBeforeApply = graphCalls
  const sqlPreviewCallsBeforeApply = sqlPreviewCalls
  await page.getByRole('button', { name: '确认应用' }).click()
  await expect.poll(() => applyBody).toEqual({
    table: 'dws_cell_hourly',
    sql: lineageSqlImportPreview.sql,
    fields: lineageSqlImportPreview.fields,
    edges: lineageSqlImportPreview.edges,
    expected_graph_version: 'v-e2e',
  })
  await expect.poll(() => graphCalls).toBeGreaterThan(graphCallsBeforeApply)
  await expect.poll(() => sqlPreviewCalls).toBeGreaterThan(sqlPreviewCallsBeforeApply)
  await expect(page.getByText('SQL 导入已应用')).toBeVisible()
})

test('lineage sql import ignores stale preview after drawer close and reopen', async ({ page }) => {
  let releasePreview: (() => void) | undefined
  await mockCommonApis(page)

  const previewRequestSeen = new Promise<void>((resolve) => {
    void page.route('**/api/lineage/sql/import/preview', async (route) => {
      resolve()
      await new Promise<void>((release) => {
        releasePreview = release
      })
      await json(route, lineageSqlImportPreview)
    })
  })

  await page.route('**/api/lineage/graph**', (route) => json(route, lineageGraph))
  await page.route('**/api/lineage/sql/preview', (route) => json(route, lineageSqlPreview))

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await page.getByRole('button', { name: '导入 SQL' }).click()
  await page.getByLabel('SQL 文本').fill('SELECT AVG(q.avg_rsrp) AS avg_rsrp FROM dwd_session_qos q GROUP BY cell_id')
  await page.getByRole('button', { name: '解析 SQL' }).click()
  await previewRequestSeen

  await page.locator('.ant-drawer-close').click()
  await page.getByRole('button', { name: '导入 SQL' }).click()
  releasePreview?.()

  await expect(page.getByText('字段变更')).toBeHidden()
  await expect(page.getByRole('button', { name: '确认应用' })).toBeHidden()
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
  await clickVisibleTableToggle(page, 'dws_cell_hourly')
  await clickVisibleTableToggle(page, 'dwd_session_qos')

  await dragVisibleSourceArrowheadToPort(page, 'dwd_session_qos', 'hour_bucket')

  await expect.poll(() => patchBody).toEqual({
    from_table: 'dwd_session_qos',
    from_field: 'hour_bucket',
    to_table: 'dws_cell_hourly',
    to_field: 'avg_rsrp',
  })
})

test('lineage workspace refetches graph and sql preview when endpoint drag fails', async ({ page }) => {
  let graphCalls = 0
  let sqlPreviewCalls = 0

  await mockCommonApis(page)
  await page.route('**/api/lineage/graph**', (route) => {
    graphCalls += 1
    return json(route, lineageGraph)
  })
  await page.route('**/api/lineage/sql/preview', (route) => {
    sqlPreviewCalls += 1
    return json(route, lineageSqlPreview)
  })
  await page.route('**/api/lineage/edges/edge-1/endpoints', async (route) => {
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'duplicate lineage edge' }),
    })
  })

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await clickVisibleTableToggle(page, 'dws_cell_hourly')
  await clickVisibleTableToggle(page, 'dwd_session_qos')
  const graphCallsBeforeMove = graphCalls
  const sqlPreviewCallsBeforeMove = sqlPreviewCalls

  await dragVisibleSourceArrowheadToPort(page, 'dwd_session_qos', 'hour_bucket')

  await expect.poll(() => graphCalls).toBeGreaterThan(graphCallsBeforeMove)
  await expect.poll(() => sqlPreviewCalls).toBeGreaterThan(sqlPreviewCallsBeforeMove)
  await expect(page.getByText(/端点更新失败/)).toBeVisible()
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
  await activateHiddenButton(page, 'expand table dws_cell_hourly')
  await activateHiddenButton(page, 'expand table dwd_session_qos')

  await activateHiddenButton(page, 'source endpoint edge-1')
  await activateHiddenButton(page, 'field port dwd_session_qos.hour_bucket')

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
  await activateHiddenButton(page, 'field edge edge-1')

  await expect(page.getByText('dwd_session_qos.avg_rsrp').last()).toBeVisible()
  await expect(page.getByText('dws_cell_hourly.avg_rsrp').last()).toBeVisible()
  await expect(page.locator('textarea').first()).toHaveValue('AVG(q.avg_rsrp)')
})

test('lineage workspace selects visible X6 field edges by click', async ({ page }) => {
  await mockCommonApis(page)

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await clickVisibleTableToggle(page, 'dws_cell_hourly')
  await clickVisibleTableToggle(page, 'dwd_session_qos')

  const fieldEdge = x6FieldEdge(page)
  await expect(fieldEdge).toBeAttached()
  await expect(x6FieldEdgePath(page)).toHaveAttribute('d', /M /)
  await expectRenderedX6PathBounds(x6FieldEdgePath(page))
  await clickRenderedX6Path(page)

  await expect(page.getByText('dwd_session_qos.avg_rsrp').last()).toBeVisible()
  await expect(page.getByText('dws_cell_hourly.avg_rsrp').last()).toBeVisible()
  await expect(page.locator('textarea').first()).toHaveValue('AVG(q.avg_rsrp)')
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
  await activateHiddenButton(page, /dwd_session_qos\.avg_rsrp.*dws_cell_hourly\.avg_rsrp/)

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
