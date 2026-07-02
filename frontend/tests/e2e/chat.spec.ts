import { expect, test } from '@playwright/test'
import { json } from './fixtures'

test('chat page renders agent step and gap proposal payload', async ({ page }) => {
  await page.route('**/api/chat/start', (route) => json(route, { session_id: 's1', context: { context: 'lineage', table: 'dws_cell_hourly' } }))
  await page.route('**/api/chat/message', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'data: {"event":"node_complete","node":"classifier"}',
        '',
        'data: {"event":"presenter_payload","summary":"建议补齐","payload":{"type":"gap_proposal_card","intent":"forward_etl","gaps":[{"type":"missing_field"}],"draft":{"operation":"ADD_FIELD"}}}',
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat?context=lineage&table=dws_cell_hourly')
  await page.getByPlaceholder('输入业务语义、元数据变更或反向合成需求').fill('按基站负载和信号质量做评估')
  await page.getByRole('button', { name: /发送/ }).click()

  await expect(page.getByText('意图识别')).toBeVisible()
  await expect(page.getByText('缺失对象补齐建议')).toBeVisible()
  await expect(page.getByText('forward_etl')).toBeVisible()
})
