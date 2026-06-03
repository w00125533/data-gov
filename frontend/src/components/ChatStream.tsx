import { Badge, Typography } from 'antd'

type ChatItem = {
  role: 'user' | 'assistant' | 'event'
  content: string
  node?: string
}

type Props = {
  items: ChatItem[]
}

export default function ChatStream({ items }: Props) {
  return (
    <div className="chat-stream">
      {items.map((item, index) => (
        <div className={`chat-message ${item.role}`} key={`${item.role}-${index}`}>
          {item.node ? <Badge color="blue" text={item.node} /> : null}
          <Typography.Paragraph style={{ margin: item.node ? '6px 0 0' : 0 }}>{item.content}</Typography.Paragraph>
        </div>
      ))}
    </div>
  )
}
