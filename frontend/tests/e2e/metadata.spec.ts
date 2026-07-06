import { expect, test } from '@playwright/test'
import { mockCommonApis } from './fixtures'

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
