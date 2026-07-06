type LineageContextTargetType = 'node' | 'edge' | 'canvas'

export type LineageMenuAction =
  | 'edit-node'
  | 'add-field'
  | 'create-downstream'
  | 'create-edge'
  | 'edit-edge'
  | 'delete-edge'
  | 'chat'
  | 'new-table'

export const LINEAGE_CONTEXT_MENU_ACTIONS: Array<{
  key: LineageMenuAction
  label: string
  targets: LineageContextTargetType[]
}> = [
  { key: 'edit-node', label: '编辑节点', targets: ['node'] },
  { key: 'add-field', label: '添加字段', targets: ['node'] },
  { key: 'create-downstream', label: '创建下游表', targets: ['node'] },
  { key: 'create-edge', label: '新建血缘边', targets: ['node', 'canvas'] },
  { key: 'edit-edge', label: '编辑边表达式', targets: ['edge'] },
  { key: 'delete-edge', label: '删除血缘边', targets: ['edge'] },
  { key: 'new-table', label: '新建表', targets: ['canvas'] },
  { key: 'chat', label: '用 NL 修改', targets: ['node', 'edge', 'canvas'] },
]
