import test from 'node:test'
import assert from 'node:assert/strict'
import { formalLineageToGraph } from './formalLineageGraphData.mjs'

test('formalLineageToGraph prefers field edges when field lineage is present', () => {
  const graph = formalLineageToGraph({
    nodes: [
      { metadataId: 'm1', assetCode: 'dwd_cell_profile', assetName: 'DWD Cell Profile' },
      { metadataId: 'm2', assetCode: 'ads_cell_profile', assetName: 'ADS Cell Profile' },
    ],
    edges: [
      {
        sourceMetadataId: 'm1',
        sourceAssetCode: 'dwd_cell_profile',
        targetMetadataId: 'm2',
        targetAssetCode: 'ads_cell_profile',
        lineageType: 'FIELD',
        direction: 'DOWN',
        expression: 'score = rsrp_avg',
      },
    ],
    fieldEdges: [
      {
        sourceMetadataId: 'm1',
        sourceAssetCode: 'dwd_cell_profile',
        sourceField: 'rsrp_avg',
        targetMetadataId: 'm2',
        targetAssetCode: 'ads_cell_profile',
        targetField: 'coverage_score',
        lineageType: 'FIELD',
        direction: 'DOWN',
        expression: 'coverage_score = rsrp_avg',
      },
    ],
  })

  assert.deepEqual(
    graph.nodes.map((node) => node.id),
    ['dwd_cell_profile.rsrp_avg', 'ads_cell_profile.coverage_score'],
  )
  assert.equal(graph.edges[0].source, 'dwd_cell_profile.rsrp_avg')
  assert.equal(graph.edges[0].target, 'ads_cell_profile.coverage_score')
  assert.equal(graph.edges[0].style.labelText, 'coverage_score = rsrp_avg')
})

test('formalLineageToGraph falls back to asset edges when field lineage is absent', () => {
  const graph = formalLineageToGraph({
    nodes: [],
    edges: [
      {
        sourceMetadataId: 'm1',
        sourceAssetCode: 'dwd_cell_profile',
        targetMetadataId: 'm2',
        targetAssetCode: 'ads_cell_profile',
        lineageType: 'TABLE',
        direction: 'DOWN',
        expression: '',
      },
    ],
    fieldEdges: [],
  })

  assert.deepEqual(
    graph.nodes.map((node) => node.id),
    ['dwd_cell_profile', 'ads_cell_profile'],
  )
  assert.equal(graph.edges[0].style.labelText, 'TABLE')
})
