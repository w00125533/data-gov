import { expect, test } from '@playwright/test'
import { json } from './fixtures'

test('lineage page shows edge details and edge editor entry', async ({ page }) => {
  await page.route('**/api/lineage**', (route) => json(route, {
    root_table: 'dws_cell_hourly',
    direction: 'down',
    depth: 5,
    edges: [{
      edge_id: 'edge-1',
      from_table: 'ods_ue_signal',
      from_field: 'rsrp',
      to_table: 'dws_cell_hourly',
      to_field: 'avg_rsrp',
      transform_expr: 'AVG(rsrp)',
      created_at: '2026-07-02T10:00:00',
    }],
  }))

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await expect(page.getByText('字段级血缘')).toBeVisible()
  await page.getByText('ods_ue_signal.rsrp').click()
  await expect(page.getByText('AVG(rsrp)')).toBeVisible()
  await page.getByRole('button', { name: '新建血缘边' }).click()
  await expect(page.getByText('新建血缘边').last()).toBeVisible()
})
