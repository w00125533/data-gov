import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import LineageSqlPanel from './LineageSqlPanel'

describe('LineageSqlPanel', () => {
  it('renders workflow actions before SQL text and warnings after SQL text', () => {
    const html = renderToStaticMarkup(
      <LineageSqlPanel
        preview={{
          table: 'dws_cell_hourly',
          sql: 'SELECT 1 AS metric',
          complete: false,
          warnings: ['SQL warning after content'],
          changed: true,
        }}
        onRefresh={vi.fn()}
        onSync={vi.fn()}
        workflowActions={(
          <>
            <button type="button">导入 SQL</button>
            <button type="button">新建血缘边</button>
            <button type="button">用 NL 修改</button>
          </>
        )}
      />,
    )

    expect(html.indexOf('生成 SQL')).toBeLessThan(html.indexOf('SELECT 1 AS metric'))
    expect(html.indexOf('导入 SQL')).toBeLessThan(html.indexOf('SELECT 1 AS metric'))
    expect(html.indexOf('新建血缘边')).toBeLessThan(html.indexOf('SELECT 1 AS metric'))
    expect(html.indexOf('用 NL 修改')).toBeLessThan(html.indexOf('SELECT 1 AS metric'))
    expect(html.indexOf('SQL warning after content')).toBeGreaterThan(html.indexOf('SELECT 1 AS metric'))
    expect(html.indexOf('生成 SQL 与当前表定义不一致')).toBeGreaterThan(html.indexOf('SELECT 1 AS metric'))
  })
})
