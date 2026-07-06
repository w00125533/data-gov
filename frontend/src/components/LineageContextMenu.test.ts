import { describe, expect, it } from 'vitest'
import { shouldCloseLineageContextMenu } from './lineageContextMenuClose'
import { LINEAGE_CONTEXT_MENU_ACTIONS } from './lineageContextMenuActions'

describe('LineageContextMenu actions', () => {
  it('exposes a create downstream table menu entry', () => {
    const labels = LINEAGE_CONTEXT_MENU_ACTIONS.map((action) => action.label)
    const keys = LINEAGE_CONTEXT_MENU_ACTIONS.map((action) => action.key)

    expect(labels).toContain('创建下游表')
    expect(keys).toContain('create-downstream')
  })

  it('closes only when focus moves outside the menu', () => {
    const inside = {} as Node
    const outside = {} as Node
    const menu = {
      contains: (target: Node) => target === inside,
    } as HTMLElement

    expect(shouldCloseLineageContextMenu(inside, menu)).toBe(false)
    expect(shouldCloseLineageContextMenu(outside, menu)).toBe(true)
    expect(shouldCloseLineageContextMenu(null, menu)).toBe(true)
  })
})
