import { Timeline, Tag, Typography } from 'antd'
import type { SchemaChange } from '../api/client'

type Props = {
  changes: SchemaChange[]
  onSelect?: (change: SchemaChange) => void
}

export default function EvolutionTimeline({ changes, onSelect }: Props) {
  return (
    <Timeline
      items={changes.map((change) => ({
        children: (
          <button className="timeline-button" type="button" onClick={() => onSelect?.(change)}>
            <Tag>{change.operation}</Tag>
            <Typography.Text strong>
              {change.table_name ? `${change.table_name}${change.field_name ? `.${change.field_name}` : ''}` : change.field_name || 'table'}
            </Typography.Text>
            <Typography.Text className="muted">{change.changed_at}</Typography.Text>
          </button>
        ),
      }))}
    />
  )
}
