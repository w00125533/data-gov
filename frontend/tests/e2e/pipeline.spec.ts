import { expect, test } from '@playwright/test'
import { json } from './fixtures'

test('pipeline reverse mode shows selected path and constraints', async ({ page }) => {
  await page.route('**/api/pipeline**', (route) => json(route, {
    mode: 'reverse',
    table: 'eval_user_score',
    depth: 3,
    nodes: [
      { id: 'ads', name: 'ads_cell_profile', layer: 'ADS', layer_priority: 4, storage_type: 'STARROCKS', description: 'profile', field_count: 3, selected: false, upstream_tables: [], downstream_tables: ['eval_user_score'] },
      { id: 'eval', name: 'eval_user_score', layer: 'EVAL', layer_priority: 5, storage_type: 'STARROCKS', description: 'score', field_count: 2, selected: true, upstream_tables: ['ads_cell_profile'], downstream_tables: [] },
    ],
    edges: [{ source: 'eval_user_score', target: 'ads_cell_profile', weight: 2, fields: ['coverage_score'], constraint_summary: 'coverage_score in [0,100]' }],
    selected_path: ['ads_cell_profile', 'eval_user_score'],
    constraints: [{ field: 'coverage_score', range: [80, 100], rows: 3, bucket: 'excellent' }],
  }))

  await page.goto('/pipeline?mode=reverse&table=eval_user_score')
  await expect(page.getByText('Pipeline 可视化')).toBeVisible()
  await expect(page.getByText('eval_user_score').first()).toBeVisible()
  await expect(page.getByText('约束反推')).toBeVisible()
  await expect(page.getByText(/coverage_score/)).toBeVisible()
})
