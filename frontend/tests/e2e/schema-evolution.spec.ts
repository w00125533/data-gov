import { expect, test } from '@playwright/test'
import { json } from './fixtures'

test('schema evolution page uses selected change for yaml diff', async ({ page }) => {
  await page.route('**/api/schema/evolution/yaml-diff**', (route) => json(route, {
    table: 'dwd_session_qos',
    version: 2,
    yaml_path: 'metadata-yaml/L2-DWD/dwd_session_qos.yaml',
    historical: 'old: value',
    current: 'new: value',
    commit_hash: 'abc123',
  }))
  await page.route('**/api/schema/evolution**', (route) => json(route, {
    table: 'dwd_session_qos',
    changes: [{
      change_id: 'chg1',
      operation: 'UPDATE_FIELD',
      table_name: 'dwd_session_qos',
      field_name: 'avg_rsrp',
      version: 2,
      previous_version: 1,
      old_value: { expression: 'AVG(rsrp)' },
      new_value: { expression: 'AVG(avg_rsrp)' },
      downstream: [{ table: 'dws_cell_hourly', field: 'avg_rsrp' }],
      changed_at: '2026-07-02T10:00:00',
      commit_hash: 'abc123',
    }],
  }))

  await page.goto('/schema-evolution?table=dwd_session_qos')
  await expect(page.getByText('UPDATE_FIELD')).toBeVisible()
  await expect(page.getByText('v1 → v2')).toBeVisible()
  await page.getByRole('button', { name: /查看 YAML diff/ }).click()
  await expect(page.locator('.ant-modal-title', { hasText: 'YAML diff' })).toBeVisible()
})
