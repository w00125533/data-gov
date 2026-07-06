import { Button, Space } from 'antd'
import { useEffect, useRef } from 'react'
import { shouldCloseLineageContextMenu } from './lineageContextMenuClose'
import { LINEAGE_CONTEXT_MENU_ACTIONS, type LineageMenuAction } from './lineageContextMenuActions'

type Props = {
  open: boolean
  x: number
  y: number
  targetType?: 'node' | 'edge' | 'canvas'
  onAction: (action: LineageMenuAction) => void
  onClose: () => void
}

export default function LineageContextMenu({ open, x, y, targetType = 'canvas', onAction, onClose }: Props) {
  const menuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return undefined

    function handlePointerDown(event: PointerEvent) {
      if (shouldCloseLineageContextMenu(event.target, menuRef.current)) {
        onClose()
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('pointerdown', handlePointerDown, true)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown, true)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [onClose, open])

  if (!open) return null
  return (
    <div ref={menuRef} className="lineage-context-menu" style={{ left: x, top: y }}>
      <Space orientation="vertical" size={4}>
        {LINEAGE_CONTEXT_MENU_ACTIONS.filter((item) => item.targets.includes(targetType)).map((item) => (
          <Button key={item.key} type="text" size="small" onClick={() => onAction(item.key)}>
            {item.label}
          </Button>
        ))}
      </Space>
    </div>
  )
}
