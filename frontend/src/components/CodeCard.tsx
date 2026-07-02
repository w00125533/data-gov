import Editor from '@monaco-editor/react'
import { Button, Space, Switch, Typography, message } from 'antd'
import { useState } from 'react'

type Props = {
  title?: string
  code: string
  language?: string
  onDryRun?: () => void
}

export default function CodeCard({ title = '代码卡片', code, language = 'sql', onDryRun }: Props) {
  const [editable, setEditable] = useState(false)
  const [apiMessage, holder] = message.useMessage()

  async function copyCode() {
    await navigator.clipboard.writeText(code)
    apiMessage.success('已复制')
  }

  return (
    <div className="code-card">
      {holder}
      <div className="toolbar panel-pad">
        <Typography.Text strong>{title}</Typography.Text>
        <Space>
          <Switch size="small" checked={editable} onChange={setEditable} checkedChildren="编辑" unCheckedChildren="只读" />
          <Button size="small" onClick={() => void copyCode()}>复制</Button>
          <Button size="small" type="primary" onClick={onDryRun}>
            沙箱试跑
          </Button>
        </Space>
      </div>
      <Editor height="260px" language={language} value={code} options={{ minimap: { enabled: false }, readOnly: !editable }} />
    </div>
  )
}
