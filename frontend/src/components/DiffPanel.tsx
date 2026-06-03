import Editor from '@monaco-editor/react'
import { Typography } from 'antd'

type Props = {
  oldValue: string
  newValue: string
}

export default function DiffPanel({ oldValue, newValue }: Props) {
  return (
    <div className="diff-grid">
      <div>
        <Typography.Text strong>旧版本</Typography.Text>
        <Editor height="280px" language="yaml" value={oldValue} options={{ readOnly: true, minimap: { enabled: false } }} />
      </div>
      <div>
        <Typography.Text strong>当前版本</Typography.Text>
        <Editor height="280px" language="yaml" value={newValue} options={{ readOnly: true, minimap: { enabled: false } }} />
      </div>
    </div>
  )
}
