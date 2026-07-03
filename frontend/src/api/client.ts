export type Layer = 'ODS' | 'DWD' | 'DWS' | 'ADS' | 'EVAL'

export type TableSummary = {
  id: string
  name: string
  layer: Layer
  layer_priority: number
  storage_type: string
  description: string
  field_count: number
}

export type UpstreamRef = {
  table: string
  field: string
}

export type FieldResponse = {
  id: string
  name: string
  field_type: string
  is_nullable: boolean
  is_partition: boolean
  expression?: string | null
  description: string
  version: number
  upstream: UpstreamRef[]
}

export type TableResponse = TableSummary & {
  fields: FieldResponse[]
}

export type CreateTablePayload = {
  name: string
  layer: Layer
  storage_type: 'KAFKA' | 'HIVE' | 'STARROCKS'
  description: string
}

export type UpdateTablePayload = Partial<Pick<CreateTablePayload, 'layer' | 'storage_type' | 'description'>>

export type CreateFieldPayload = {
  table_id: string
  name: string
  field_type: string
  is_nullable: boolean
  is_partition: boolean
  expression?: string | null
  description: string
  upstream: UpstreamRef[]
}

export type UpdateFieldPayload = Partial<Omit<CreateFieldPayload, 'table_id' | 'name'>>

export type SchemaApplyPayload = {
  diff: Array<Record<string, unknown>>
}

export type CalcType = 'DIRECT' | 'EXPRESSION' | 'AGGREGATE' | 'JOIN' | 'WINDOW' | 'CONDITION' | 'CONSTANT'

export type LineageEdge = {
  edge_id?: string
  from_table: string
  from_field: string
  to_table: string
  to_field: string
  transform_expr: string
  calc_type?: CalcType
  calc_params?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export type LineageResponse = {
  root_table: string
  direction: 'up' | 'down'
  depth: number
  edges: LineageEdge[]
}

export type LineageTableNode = TableSummary & {
  fields: FieldResponse[]
  sql_logic?: string | null
  sql_dialect?: string | null
  sql_source?: 'generated' | 'imported' | 'manual' | null
  sql_updated_at?: string
}

export type LineageTableEdge = {
  source: string
  target: string
  direction: 'upstream' | 'downstream'
  field_edge_count: number
  calc_type_counts: Record<string, number>
  fields: string[]
}

export type LineageGraphResponse = {
  root_table: string
  depth: number
  include_upstream: boolean
  include_downstream: boolean
  graph_version: string
  tables: LineageTableNode[]
  table_edges: LineageTableEdge[]
  field_edges: LineageEdge[]
  saved_sql?: string | null
}

export type LineageSqlPreviewResponse = {
  table: string
  sql: string
  complete: boolean
  warnings: string[]
  saved_sql?: string | null
  changed: boolean
}

export type FieldChangePreview = {
  action: 'add' | 'update' | 'keep'
  field: string
  expression: string
  field_type: string
  upstream: UpstreamRef[]
}

export type EdgeChangePreview = {
  action: 'add' | 'update' | 'delete' | 'keep'
  edge: LineageEdge
}

export type LineageSqlImportPreviewResponse = {
  table: string
  sql: string
  fields: FieldChangePreview[]
  edges: EdgeChangePreview[]
  warnings: string[]
}

export type PipelineResponse = {
  mode: 'forward' | 'reverse'
  table?: string | null
  depth: number
  nodes: Array<TableSummary & { selected?: boolean; upstream_tables?: string[]; downstream_tables?: string[] }>
  edges: Array<{ source: string; target: string; weight: number; fields?: string[]; constraint_summary?: string }>
  selected_path: string[]
  constraints: Array<{ field: string; range: [number, number] | number[]; rows: number; bucket: string }>
}

export type YamlFile = {
  table: string
  path: string
  content: string
}

export type YamlExportResponse = {
  table?: string | null
  files: YamlFile[]
}

export type SchemaChange = {
  change_id: string
  operation: string
  table_name?: string | null
  field_name?: string | null
  version?: number | null
  previous_version?: number | null
  old_value?: unknown
  new_value?: unknown
  downstream?: Array<{ table?: string; field?: string }>
  changed_at: string
  commit_hash?: string | null
}

export type ImpactResponse = {
  table: string
  field?: string | null
  has_downstream: boolean
  affected_tables: string[]
  downstream: LineageEdge[]
}

export type LineageEdgePayload = {
  from_table: string
  from_field: string
  to_table: string
  to_field: string
  transform_expr: string
  calc_type?: CalcType
  calc_params?: Record<string, unknown>
}

export type LineageEdgeUpdatePayload = Pick<LineageEdgePayload, 'transform_expr' | 'calc_type' | 'calc_params'>

export type HealthPayload = {
  status: string
  components?: Record<string, { status: string; detail?: string }>
}

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

function qs(params: Record<string, string | number | boolean | undefined | null>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  })
  const out = search.toString()
  return out ? `?${out}` : ''
}

export const api = {
  tables: (params: { layer?: string; search?: string } = {}) =>
    fetchJson<TableSummary[]>(`/api/tables${qs(params)}`),
  table: (id: string) => fetchJson<TableResponse>(`/api/tables/${id}`),
  createTable: (payload: CreateTablePayload) =>
    fetchJson<TableResponse>('/api/tables', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateTable: (id: string, payload: UpdateTablePayload) =>
    fetchJson<TableResponse>(`/api/tables/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteTable: (id: string) =>
    fetch(`${API_BASE}/api/tables/${id}`, { method: 'DELETE' }).then((res) => {
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    }),
  createField: (payload: CreateFieldPayload) =>
    fetchJson<FieldResponse>('/api/fields', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateField: (id: string, payload: UpdateFieldPayload) =>
    fetchJson<FieldResponse>(`/api/fields/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteField: (id: string) =>
    fetch(`${API_BASE}/api/fields/${id}`, { method: 'DELETE' }).then(async (res) => {
      if (!res.ok) throw new Error(await res.text())
    }),
  impact: (params: { table: string; field?: string | null }) =>
    fetchJson<ImpactResponse>(`/api/metadata/impact${qs(params)}`),
  applySchema: (payload: SchemaApplyPayload) =>
    fetchJson<{ passed: boolean; errors: unknown[]; warnings: unknown[]; applied: unknown[] }>('/api/schema/apply', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  lineage: (params: { table: string; direction?: 'up' | 'down'; depth?: number }) =>
    fetchJson<LineageResponse>(`/api/lineage${qs(params)}`),
  lineageGraph: (params: { table: string; depth?: number; include_upstream?: boolean; include_downstream?: boolean }) =>
    fetchJson<LineageGraphResponse>(`/api/lineage/graph${qs(params)}`),
  createLineageEdge: (payload: LineageEdgePayload) =>
    fetchJson<LineageEdge>('/api/lineage/edges', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateLineageEdge: (edgeId: string, payload: LineageEdgeUpdatePayload) =>
    fetchJson<LineageEdge>(`/api/lineage/edges/${encodeURIComponent(edgeId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  updateLineageEdgeEndpoints: (
    edgeId: string,
    payload: Pick<LineageEdgePayload, 'from_table' | 'from_field' | 'to_table' | 'to_field'>,
  ) =>
    fetchJson<LineageEdge>(`/api/lineage/edges/${encodeURIComponent(edgeId)}/endpoints`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteLineageEdge: (edgeId: string) =>
    fetch(`${API_BASE}/api/lineage/edges/${encodeURIComponent(edgeId)}`, { method: 'DELETE' }).then(async (res) => {
      if (!res.ok) throw new Error(await res.text())
    }),
  previewLineageSql: (payload: { table: string; field_edges?: LineageEdge[] }) =>
    fetchJson<LineageSqlPreviewResponse>('/api/lineage/sql/preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  previewLineageSqlImport: (payload: { table: string; sql: string }) =>
    fetchJson<LineageSqlImportPreviewResponse>('/api/lineage/sql/import/preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  applyLineageSql: (payload: {
    table: string
    sql: string
    fields: FieldChangePreview[]
    edges: EdgeChangePreview[]
    expected_graph_version?: string
  }) =>
    fetchJson<LineageSqlPreviewResponse>('/api/lineage/sql/apply', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  pipeline: (params: { mode?: 'forward' | 'reverse'; table?: string | null; depth?: number } = {}) =>
    fetchJson<PipelineResponse>(`/api/pipeline${qs(params)}`),
  yamlPreview: (table: string) => fetchJson<YamlFile>(`/api/yaml/preview/${table}`),
  yamlExport: (table?: string | null) => fetchJson<YamlExportResponse>(`/api/yaml/export${qs({ table })}`),
  health: () => fetchJson<HealthPayload>('/api/health'),
  schemaEvolution: (table: string) =>
    fetchJson<{ table: string; changes: SchemaChange[] }>(`/api/schema/evolution/${table}`),
  schemaEvolutionList: (params: { table?: string; operation?: string; q?: string } = {}) =>
    fetchJson<{ table?: string | null; changes: SchemaChange[] }>(`/api/schema/evolution${qs(params)}`),
  yamlDiff: (table: string, version: number) =>
    fetchJson<{
      table: string
      version: number
      yaml_path: string
      current: string
      historical: string
      commit_hash?: string | null
    }>(`/api/schema/evolution/yaml-diff${qs({ table_name: table, version })}`),
  chatStart: (context: Record<string, string>) =>
    fetchJson<{ session_id: string; context: Record<string, string> }>('/api/chat/start', {
      method: 'POST',
      body: JSON.stringify(context),
    }),
}
