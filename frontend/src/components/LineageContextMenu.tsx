import { Button, Space } from 'antd'

export type LineageMenuAction = 'edit-node' | 'add-field' | 'create-downstream' | 'create-edge' | 'edit-edge' | 'delete-edge' | 'chat' | 'new-table'

type Props = {
  open: boolean
  x: number
  y: number
  targetType?: 'node' | 'edge' | 'canvas'
  onAction: (action: LineageMenuAction) => void
  onClose: () => void
}

export default function LineageContextMenu({ open, x, y, targetType = 'canvas', onAction, onClose }: Props) {
  if (!open) return null
  const actions: Array<{ key: LineageMenuAction; label: string; targets: Array<Props['targetType']> }> = [
    { key: 'edit-node', label: '编辑节点', targets: ['node'] },
    { key: 'add-field', label: '添加字段', targets: ['node'] },
    { key: 'create-downstream', label: '创建下游表', targets: ['node'] },
    { key: 'create-edge', label: '新建血缘边', targets: ['node', 'canvas'] },
    { key: 'edit-edge', label: '编辑边表达式', targets: ['edge'] },
    { key: 'delete-edge', label: '删除血缘边', targets: ['edge'] },
    { key: 'new-table', label: '新建表', targets: ['canvas'] },
    { key: 'chat', label: '用 NL 修改', targets: ['node', 'edge', 'canvas'] },
  ]
  return (
    <div className="lineage-context-menu" style={{ left: x, top: y }} onMouseLeave={onClose}>
      <Space direction="vertical" size={4}>
        {actions.filter((item) => item.targets.includes(targetType)).map((item) => (
          <Button key={item.key} type="text" size="small" onClick={() => onAction(item.key)}>
            {item.label}
          </Button>
        ))}
      </Space>
    </div>
  )
}
