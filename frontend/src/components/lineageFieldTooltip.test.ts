import { describe, expect, it } from 'vitest'
import type { LineageEdge } from '../api/client'
import { formatLineageFieldTooltip } from './lineageFieldTooltip'

describe('formatLineageFieldTooltip', () => {
  it('shows only the transform expression', () => {
    const edge: LineageEdge = {
      from_table: 'ods_ue_signal',
      from_field: 'rsrp',
      to_table: 'dwd_session_qos',
      to_field: 'avg_rsrp',
      calc_type: 'AGGREGATE',
      transform_expr: 'AVG(rsrp)',
    }

    expect(formatLineageFieldTooltip(edge)).toBe('AVG(rsrp)')
  })

  it('uses a compact placeholder when expression is empty', () => {
    expect(formatLineageFieldTooltip({
      from_table: 'a',
      from_field: 'x',
      to_table: 'b',
      to_field: 'y',
      transform_expr: '',
    })).toBe('-')
  })
})
