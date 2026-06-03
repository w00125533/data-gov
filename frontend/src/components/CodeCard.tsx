import Editor from '@monaco-editor/react'
import { Button, Space, Typography } from 'antd'

type Props = {
  title?: string
  code: string
  language?: string
  onDryRun?: () => void
}

export default function CodeCard({ title = '代码卡片', code, language = 'sql', onDryRun }: Props) {
  return (
    <div className="code-card">
      <div className="toolbar panel-pad">
        <Typography.Text strong>{title}</Typography.Text>
        <Space>
          <Button size="small">复制</Button>
          <Button size="small" type="primary" onClick={onDryRun}>
            沙箱试跑
          </Button>
        </Space>
      </div>
      <Editor height="260px" language={language} value={code} options={{ minimap: { enabled: false }, readOnly: false }} />
    </div>
  )
}
