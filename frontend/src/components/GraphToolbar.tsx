import { FullscreenOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, Space, Tooltip } from 'antd'
import type { ReactNode } from 'react'

type Props = {
  onFit?: () => void
  onFullscreen?: () => void
  extra?: ReactNode
}

export default function GraphToolbar({ onFit, onFullscreen, extra }: Props) {
  return (
    <div className="graph-toolbar">
      <Space size={6}>
        <Tooltip title="适配画布">
          <Button size="small" icon={<ReloadOutlined />} onClick={onFit} />
        </Tooltip>
        <Tooltip title="全屏">
          <Button size="small" icon={<FullscreenOutlined />} onClick={onFullscreen} />
        </Tooltip>
        {extra}
      </Space>
    </div>
  )
}
