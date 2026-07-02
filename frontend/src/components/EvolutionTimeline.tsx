import type { SchemaChange } from '../api/client'
import { Timeline } from 'antd'
import SchemaChangeCard from './SchemaChangeCard'

type Props = {
  changes: SchemaChange[]
  onSelect?: (change: SchemaChange) => void
}

export default function EvolutionTimeline({ changes, onSelect }: Props) {
  return (
    <Timeline
      items={changes.map((change) => ({
        children: (
          <SchemaChangeCard change={change} onYamlDiff={onSelect} />
        ),
      }))}
    />
  )
}
