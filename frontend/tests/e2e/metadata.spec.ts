import { expect, test } from '@playwright/test'
import { mockCommonApis } from './fixtures'

test('metadata page exposes management interactions', async ({ page }) => {
  await mockCommonApis(page)
  await page.goto('/metadata')

  await expect(page.getByText('元数据管理')).toBeVisible()
  await expect(page.getByText('dws_cell_hourly').first()).toBeVisible()
  await expect(page.getByText('avg_rsrp', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: /导出 YAML/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /导出单表/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /创建下游表/ })).toBeVisible()
})
