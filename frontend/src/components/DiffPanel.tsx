import Editor from '@monaco-editor/react'
import { Typography } from 'antd'

type Props = {
  oldValue: string
  newValue: string
  oldLabel?: string
  newLabel?: string
}

export default function DiffPanel({ oldValue, newValue, oldLabel = '旧版本', newLabel = '当前版本' }: Props) {
  return (
    <div className="diff-grid">
      <div>
        <Typography.Text strong>{oldLabel}</Typography.Text>
        <Editor height="280px" language="yaml" value={oldValue} options={{ readOnly: true, minimap: { enabled: false } }} />
      </div>
      <div>
        <Typography.Text strong>{newLabel}</Typography.Text>
        <Editor height="280px" language="yaml" value={newValue} options={{ readOnly: true, minimap: { enabled: false } }} />
      </div>
    </div>
  )
}
