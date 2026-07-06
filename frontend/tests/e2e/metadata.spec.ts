import { expect, test } from '@playwright/test'
import { mockCommonApis, tables } from './fixtures'

test('metadata page exposes taxonomy navigation and table chips', async ({ page }) => {
  await mockCommonApis(page)
  await page.goto('/metadata')

  await expect(page.getByText('元数据管理')).toBeVisible()
  await expect(page.getByRole('treeitem', { name: /网络/ })).toBeVisible()
  await expect(page.getByRole('treeitem', { name: /覆盖/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /管理分类/ })).toBeVisible()
  await expect(page.getByText('dws_cell_hourly').first()).toBeVisible()
  await expect(page.getByText('网络 / 覆盖').first()).toBeVisible()
  await expect(page.getByText('质量').first()).toBeVisible()

  await page.getByRole('treeitem', { name: /质量/ }).click()
  await expect(page).toHaveURL(/category_id=category%3Anetwork\.quality/)
})

test('metadata filters realign stale selected table', async ({ page }) => {
  await mockCommonApis(page)
  await page.route('**/api/tables?*', (route) => {
    const url = new URL(route.request().url())
    const search = url.searchParams.get('search')
    const categoryId = url.searchParams.get('category_id')
    const filtered = tables.filter((table) => {
      if (search && !table.name.includes(search)) return false
      if (categoryId && table.category?.id !== categoryId) return false
      return true
    })

    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(filtered),
    })
  })
  await page.goto('/metadata')

  await page.getByRole('button', { name: /dwd_session_qos DWD/ }).click()
  await expect(page.getByRole('heading', { name: 'dwd_session_qos' })).toBeVisible()

  await page.getByPlaceholder('表名/字段/描述').fill('dws')
  await page.getByPlaceholder('表名/字段/描述').press('Enter')

  await expect(page.getByText('dws_cell_hourly').first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'dws_cell_hourly' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'dwd_session_qos' })).toHaveCount(0)
})

test('metadata page edits taxonomy and table classification', async ({ page }) => {
  await mockCommonApis(page)
  let resolveFinalTable: ((value?: unknown) => void) | undefined
  const finalTableReady = new Promise((resolve) => {
    resolveFinalTable = resolve
  })
  let tableFetchCount = 0
  const requests: string[] = []
  await page.route('**/api/tables/t1', async (route) => {
    if (route.request().method() === 'PUT') {
      requests.push('update-table')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(tables[0]),
      })
      return
    }
    tableFetchCount += 1
    if (tableFetchCount > 1) {
      requests.push('final-table')
      await finalTableReady
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...tables[0],
          category: {
            id: 'category:network.quality',
            code: 'network.quality',
            name: 'Quality',
            path: ['Network', 'Quality'],
            active: true,
          },
          fields: [],
        }),
      })
      return
    }
    await route.fallback()
  })
  await page.route('**/api/tables/t1/classification', async (route) => {
    requests.push('classification')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(tables[0]),
    })
  })

  await page.goto('/metadata')

  await page.getByRole('button', { name: /管理分类/ }).click()
  await expect(page.getByRole('tab', { name: '分类' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '标签' })).toBeVisible()
  await expect(page.getByRole('button', { name: /新增小分类/ })).toBeVisible()
  await page.getByRole('tab', { name: '标签' }).click()
  await expect(page.getByText('网络域').first()).toBeVisible()
  await expect(page.getByRole('switch', { name: /网络域/ })).toBeVisible()
  await page.getByRole('button', { name: /关闭/ }).click()

  await page.getByRole('button', { name: /编辑表/ }).click()
  await expect(page.getByRole('combobox', { name: '主分类' })).toHaveAttribute('aria-required', 'true')
  await expect(page.locator('#category_id').locator('..').getByLabel('close')).toHaveCount(0)
  await page.getByRole('combobox', { name: '主分类' }).click()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await page.getByRole('combobox', { name: '标签' }).click()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '保存分类' }).click()
  await expect(page.getByRole('button', { name: '保存分类' })).toBeVisible()
  resolveFinalTable?.()

  await expect(page.getByText('网络 / 质量').first()).toBeVisible()
  await expect.poll(() => requests).toEqual(['update-table', 'classification', 'final-table'])
})
