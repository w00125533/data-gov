import { expect, test } from '@playwright/test'

const metadataList = {
  items: [
    {
      metadataId: 'asset_ads',
      assetCode: 'ads_cell_profile',
      assetName: 'ADS Cell Profile',
      metadataType: 'TABLE',
      sourceType: 'STARROCKS',
      domain: 'wireless-rno',
      owner: 'network-team',
      queryable: true,
    },
    {
      metadataId: 'asset_dwd',
      assetCode: 'dwd_cell_profile',
      assetName: 'DWD Cell Profile',
      metadataType: 'TABLE',
      sourceType: 'HIVE',
      domain: 'wireless-rno',
      owner: 'network-team',
      queryable: true,
    },
  ],
  page: 1,
  size: 20,
  total: 2,
}

test.beforeEach(async ({ page }) => {
  await page.route('**/rest/oss/inner/modelengineservice/v1/metadata?**', async (route) => {
    await route.fulfill({ json: metadataList })
  })

  await page.route('**/rest/oss/inner/modelengineservice/v1/metadata/asset_ads/lineage?**', async (route) => {
    const direction = new URL(route.request().url()).searchParams.get('direction')?.toUpperCase() ?? 'DOWN'
    await route.fulfill({
      json: {
        metadataId: 'asset_ads',
        direction,
        depth: 5,
        nodes: metadataList.items.map(({ metadataId, assetCode, assetName }) => ({ metadataId, assetCode, assetName })),
        edges: [
          {
            sourceMetadataId: 'asset_dwd',
            sourceAssetCode: 'dwd_cell_profile',
            targetMetadataId: 'asset_ads',
            targetAssetCode: 'ads_cell_profile',
            lineageType: 'FIELD',
            direction,
            expression: 'job:rno-profile-etl',
          },
        ],
        fieldEdges: [
          {
            sourceMetadataId: 'asset_dwd',
            sourceAssetCode: 'dwd_cell_profile',
            sourceField: 'rsrp_avg',
            targetMetadataId: 'asset_ads',
            targetAssetCode: 'ads_cell_profile',
            targetField: 'coverage_score',
            lineageType: 'FIELD',
            direction,
            expression: 'case when rsrp_avg >= -95 then 100 else 60 end',
          },
        ],
      },
    })
  })
})

test('正式血缘验收：搜索资产、加载字段级血缘并查看边详情', async ({ page }) => {
  await page.goto('/metadata/lineage?source=formal')

  await expect(page.getByRole('heading', { name: '血缘图' })).toBeVisible()
  await expect(page.getByText('正式元数据')).toBeVisible()

  await page.getByPlaceholder('搜索资产编码/名称').fill('ads_cell_profile')
  await page.getByPlaceholder('搜索资产编码/名称').press('Enter')
  await page.getByTestId('formal-asset-asset_ads').click()

  await expect(page.getByTestId('formal-current-metadata')).toContainText('当前资产')
  await expect(page.getByTestId('formal-current-metadata')).toContainText('ads_cell_profile')
  await expect(page.getByTestId('formal-field-edge-count')).toContainText('1')

  await page.getByTestId('formal-field-edge-rsrp_avg-coverage_score').click()

  await expect(page.getByTestId('formal-selected-edge')).toContainText('字段级')
  await expect(page.getByTestId('formal-selected-edge')).toContainText('dwd_cell_profile.rsrp_avg')
  await expect(page.getByTestId('formal-selected-edge')).toContainText('ads_cell_profile.coverage_score')
  await expect(page.getByTestId('formal-selected-edge')).toContainText('case when rsrp_avg >= -95 then 100 else 60 end')
})
