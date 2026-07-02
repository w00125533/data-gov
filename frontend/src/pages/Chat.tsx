import { AlertOutlined, CheckCircleOutlined, SendOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Input, Space, Tag, Typography } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import AgentStepper from '../components/AgentStepper'
import ChatStream from '../components/ChatStream'
import CodeCard from '../components/CodeCard'
import ConstraintSlider from '../components/ConstraintSlider'
import DiffPanel from '../components/DiffPanel'
import DryRunPreview from '../components/DryRunPreview'
import GapProposalCard from '../components/GapProposalCard'
import ReverseSynthesisPanel from '../components/ReverseSynthesisPanel'

type ChatItem = {
  role: 'user' | 'assistant' | 'event'
  content: string
  node?: string
}

type PresenterPayload = {
  type?: string
  summary?: string
  code?: string
  code_type?: string
  preview_row?: Record<string, unknown>
  success?: boolean
  error_log?: string
  applied?: Array<Record<string, unknown>>
  warnings?: unknown[]
  errors?: unknown[]
  intent?: string
  gaps?: unknown[]
  draft?: unknown
  constraints?: Array<{ field: string; range: [number, number] | number[]; rows: number; bucket: string }>
}

function ResultPanel({ payload }: { payload?: PresenterPayload }) {
  if (!payload) {
    return (
      <Space direction="vertical" style={{ width: '100%' }} size={14}>
        <Alert type="info" message="等待 Agent 结果" showIcon />
        <ConstraintSlider label="优秀样本 qoe_score" value={[80, 100]} rows={3} />
      </Space>
    )
  }

  if (payload.type === 'code_card') {
    return (
      <Space direction="vertical" style={{ width: '100%' }} size={14}>
        <Tag color={payload.success ? 'success' : 'error'} icon={payload.success ? <CheckCircleOutlined /> : <AlertOutlined />}>
          {payload.success ? '执行成功' : '执行失败'}
        </Tag>
        <CodeCard
          title={payload.code_type ?? '生成代码'}
          code={payload.code ?? ''}
          language={payload.code_type?.includes('java') ? 'java' : 'sql'}
        />
        <DryRunPreview row={payload.preview_row} />
        {payload.error_log ? <Alert type="error" message="错误日志" description={payload.error_log} /> : null}
      </Space>
    )
  }

  if (payload.type === 'schema_diff_card') {
    return (
      <Space direction="vertical" style={{ width: '100%' }} size={14}>
        <Alert type="success" message="元数据变更已应用" showIcon />
        {payload.applied?.map((change, index) => (
          <Card size="small" key={`${change.change_id ?? index}`}>
            <Typography.Text strong>{String(change.operation ?? 'CHANGE')}</Typography.Text>
            <Typography.Paragraph className="muted" style={{ marginBottom: 0 }}>
              {String(change.table ?? '')}{change.field ? `.${String(change.field)}` : ''}
            </Typography.Paragraph>
          </Card>
        ))}
        {payload.warnings?.length ? <Alert type="warning" message="影响提示" description={JSON.stringify(payload.warnings)} /> : null}
      </Space>
    )
  }

  if (payload.type === 'gap_proposal_card') {
    return <GapProposalCard gaps={payload.gaps} draft={payload.draft} />
  }

  if (payload.type === 'reverse_constraints' || payload.constraints?.length) {
    return <ReverseSynthesisPanel constraints={payload.constraints ?? []} />
  }

  if (payload.type === 'clarification') {
    return <Alert type="warning" message="需要补充信息" description={payload.summary} showIcon />
  }

  if (payload.type === 'error') {
    return (
      <Space direction="vertical" style={{ width: '100%' }} size={14}>
        <Alert type="error" message={payload.summary ?? '执行失败'} description={payload.errors ? JSON.stringify(payload.errors) : undefined} showIcon />
        <DiffPanel oldValue="" newValue={JSON.stringify(payload, null, 2)} />
      </Space>
    )
  }

  return <Alert type="info" message={payload.summary ?? '已完成'} description={JSON.stringify(payload, null, 2)} />
}

export default function Chat() {
  const [params] = useSearchParams()
  const context = useMemo(() => Object.fromEntries(params.entries()), [params])
  const [sessionId, setSessionId] = useState<string>()
  const [input, setInput] = useState('')
  const [items, setItems] = useState<ChatItem[]>([])
  const [streaming, setStreaming] = useState(false)
  const [resultPayload, setResultPayload] = useState<PresenterPayload>()
  const [completedNodes, setCompletedNodes] = useState<string[]>([])

  useEffect(() => {
    api.chatStart(context)
      .then((payload) => {
        setSessionId(payload.session_id)
        if (Object.keys(payload.context).length) {
          setItems([{ role: 'event', content: `上下文已注入: ${JSON.stringify(payload.context)}` }])
        }
      })
      .catch((error) => {
        setItems((prev) => [...prev, { role: 'event', content: `新建对话失败: ${error.message}` }])
      })
  }, [context])

  async function sendMessage() {
    if (!sessionId || !input.trim()) return
    const content = input.trim()
    setInput('')
    setResultPayload(undefined)
    setCompletedNodes([])
    setItems((prev) => [...prev, { role: 'user', content }])
    setStreaming(true)
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE ?? ''}/api/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, content }),
      })
      if (!response.ok) throw new Error(await response.text())
      if (!response.body) throw new Error('empty stream')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() ?? ''
        chunks.forEach((chunk) => {
          const dataLine = chunk.split('\n').find((line) => line.startsWith('data:'))
          if (!dataLine) return
          const payload = JSON.parse(dataLine.slice(5))
          if (payload.event === 'node_complete') {
            setCompletedNodes((prev) => [...prev, payload.node])
            setItems((prev) => [...prev, { role: 'event', node: payload.node, content: '节点执行完成' }])
          }
          if (payload.event === 'presenter_payload') {
            setResultPayload(payload.payload)
            setItems((prev) => [...prev, { role: 'assistant', content: payload.summary }])
          }
          if (payload.event === 'error') {
            setItems((prev) => [...prev, { role: 'event', content: payload.detail }])
          }
        })
      }
    } catch (error) {
      setItems((prev) => [...prev, { role: 'event', content: `发送失败: ${(error as Error).message}` }])
    } finally {
      setStreaming(false)
    }
  }

  return (
    <div className="chat-layout">
      <section>
        <div className="toolbar">
          <div>
            <Typography.Title level={3} style={{ margin: 0 }}>NL 对话</Typography.Title>
            <Typography.Text className="muted">Session: {sessionId ?? 'creating...'}</Typography.Text>
          </div>
        </div>
        {Object.keys(context).length ? (
          <Alert style={{ marginBottom: 12 }} type="info" message={`来自页面跳转的上下文: ${JSON.stringify(context)}`} />
        ) : null}
        <ChatStream items={items} />
        <Space.Compact style={{ width: '100%', marginTop: 12 }}>
          <Input.TextArea
            value={input}
            autoSize={{ minRows: 1, maxRows: 4 }}
            placeholder="输入业务语义、元数据变更或反向合成需求"
            onChange={(event) => setInput(event.target.value)}
            onPressEnter={(event) => {
              if (!event.shiftKey) {
                event.preventDefault()
                void sendMessage()
              }
            }}
          />
          <Button type="primary" icon={<SendOutlined />} loading={streaming} onClick={() => void sendMessage()}>
            发送
          </Button>
        </Space.Compact>
      </section>
      <aside className="panel panel-pad">
        <Space direction="vertical" style={{ width: '100%' }} size={14}>
          <div className="toolbar">
            <Typography.Title level={4} style={{ marginTop: 0, marginBottom: 0 }}>结果面板</Typography.Title>
            {resultPayload?.intent ? <Tag color="blue">{resultPayload.intent}</Tag> : null}
          </div>
          {completedNodes.length ? <AgentStepper nodes={completedNodes} /> : null}
        </Space>
        <ResultPanel payload={resultPayload} />
      </aside>
    </div>
  )
}
