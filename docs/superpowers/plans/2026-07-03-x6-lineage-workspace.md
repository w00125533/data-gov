# X6 Lineage Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current DOM/list-based lineage workspace canvas with an AntV X6 editable graph that renders table nodes, curved lineage edges, expandable field rows, field ports, dashed field-level edges, edge selection, endpoint reconnection, and SQL preview refresh.

**Architecture:** The backend lineage graph contract is already in place and remains unchanged. The frontend keeps the existing three-panel `/metadata/lineage` page: left filters and right edge/SQL panels stay React/Ant Design, while the center `LineageWorkspaceGraph` becomes an X6 graph driven by a pure `LineageGraphResponse -> X6 cells` adapter. X6 owns visual graph rendering and edge endpoint reconnection; React owns query state, expanded table state, selected edge state, mutations, toasts, and SQL preview invalidation.

**Tech Stack:** React 18, TypeScript, Vite, Ant Design, AntV X6, AntV X6 MiniMap plugin, React Query, Playwright, Vitest.

---

## References

- Design spec: `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md`, especially sections 6.4, 6.5, 6.8, and acceptance items P3-6 through P3-10c.
- Existing page: `frontend/src/pages/Lineage.tsx`.
- Current center canvas boundary: `frontend/src/components/LineageWorkspaceGraph.tsx`.
- Existing data helper: `frontend/src/components/graphShared/lineageWorkspaceData.ts`.
- Existing API contract: `frontend/src/api/client.ts`.
- Existing e2e fixture and tests: `frontend/tests/e2e/fixtures.ts`, `frontend/tests/e2e/lineage.spec.ts`.
- Pipeline G6 example kept as read-only reference only: `frontend/src/components/PipelineDAG.tsx`.

## Scope Boundaries

- Do not change backend APIs, Neo4j persistence, SQL preview/import services, or `/pipeline`.
- Do not introduce `@antv/x6-react-shape` in this first X6 implementation.
- Do not add copy/paste, undo/redo, lasso selection, or multi-edge batch editing.
- Keep the right-side `LineageEdgeEditor`, `LineageSqlPanel`, and `LineageSqlImportDrawer` behavior unchanged except for receiving selected edges from X6.
- Keep keyboard fallback for endpoint movement so e2e can validate the same API payload without depending only on pixel drag behavior.
- Use X6 for visible lineage graph rendering; semantic hidden controls are allowed only for accessibility and deterministic e2e interaction.

## File Structure

- Modify `frontend/package.json`: add `@antv/x6`, `@antv/x6-plugin-minimap`, `vitest`, and `test:unit`.
- Modify `frontend/package-lock.json`: dependency lock update from `npm install`.
- Create `frontend/src/components/graphShared/lineageX6Adapter.ts`: pure layout and X6 cell adapter; no React imports.
- Create `frontend/src/components/graphShared/lineageX6Adapter.test.ts`: Vitest tests for table layout, ports, edge ids, and direction filtering.
- Replace internals of `frontend/src/components/LineageWorkspaceGraph.tsx`: instantiate X6 `Graph`, render cells, register graph events, expose semantic keyboard controls, and preserve existing props.
- Modify `frontend/src/pages/Lineage.tsx`: pass selected edge to the X6 component and keep mutation/SQL refresh wiring.
- Modify `frontend/src/styles.css`: replace DOM grid/list graph styles with X6 shell, canvas, minimap, tooltip, and hidden accessibility controls.
- Modify `frontend/tests/e2e/lineage.spec.ts`: assert X6 canvas rendering, table and field edge behavior, edge selection, endpoint mutation, and direction filtering.

## Task 1: Add X6 Dependencies And Unit Test Harness

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [ ] **Step 1: Install graph and unit-test dependencies**

Run:

```powershell
npm.cmd --prefix frontend install @antv/x6 @antv/x6-plugin-minimap
npm.cmd --prefix frontend install -D vitest
```

Expected: `frontend/package.json` contains `@antv/x6` and `@antv/x6-plugin-minimap` under `dependencies`, and `vitest` under `devDependencies`. `frontend/package-lock.json` is updated.

- [ ] **Step 2: Add unit-test script**

In `frontend/package.json`, add this script next to `test:e2e`:

```json
"test:unit": "vitest run"
```

Expected scripts block contains:

```json
{
  "lint": "eslint .",
  "preview": "vite preview",
  "test:unit": "vitest run",
  "test:e2e": "playwright test",
  "test:e2e:ui": "playwright test --ui"
}
```

- [ ] **Step 3: Verify the empty unit test harness**

Run:

```powershell
npm.cmd --prefix frontend run test:unit -- --passWithNoTests
```

Expected: Vitest exits 0 and reports no test files or no tests found.

- [ ] **Step 4: Commit dependency setup**

Run:

```powershell
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add x6 lineage graph dependencies"
```

Expected: one commit containing only frontend dependency and script changes.

## Task 2: Build Pure X6 Graph Adapter

**Files:**
- Create: `frontend/src/components/graphShared/lineageX6Adapter.ts`
- Create: `frontend/src/components/graphShared/lineageX6Adapter.test.ts`

- [ ] **Step 1: Write failing adapter tests**

Create `frontend/src/components/graphShared/lineageX6Adapter.test.ts`:

```ts
import { describe, expect, test } from 'vitest'
import type { LineageGraphResponse } from '../../api/client'
import {
  buildLineageX6GraphData,
  edgeKey,
  fieldEdgeCellId,
  fieldPortId,
  tableEdgeCellId,
} from './lineageX6Adapter'

const payload: LineageGraphResponse = {
  root_table: 'dws_cell_hourly',
  depth: 2,
  include_upstream: true,
  include_downstream: true,
  graph_version: 'v-test',
  saved_sql: null,
  tables: [
    {
      id: 't-root',
      name: 'dws_cell_hourly',
      layer: 'DWS',
      layer_priority: 3,
      storage_type: 'HIVE',
      description: 'cell hourly',
      field_count: 2,
      sql_logic: null,
      sql_dialect: null,
      sql_source: null,
      sql_updated_at: '',
      fields: [
        {
          id: 'f-root-1',
          name: 'avg_rsrp',
          field_type: 'DOUBLE',
          is_nullable: true,
          is_partition: false,
          expression: 'AVG(q.avg_rsrp)',
          description: 'avg rsrp',
          version: 1,
          upstream: [],
        },
        {
          id: 'f-root-2',
          name: 'hour_bucket',
          field_type: 'TIMESTAMP',
          is_nullable: false,
          is_partition: true,
          expression: null,
          description: 'hour',
          version: 1,
          upstream: [],
        },
      ],
    },
    {
      id: 't-up',
      name: 'dwd_session_qos',
      layer: 'DWD',
      layer_priority: 2,
      storage_type: 'HIVE',
      description: 'qos',
      field_count: 2,
      sql_logic: null,
      sql_dialect: null,
      sql_source: null,
      sql_updated_at: '',
      fields: [
        {
          id: 'f-up-1',
          name: 'avg_rsrp',
          field_type: 'DOUBLE',
          is_nullable: true,
          is_partition: false,
          expression: null,
          description: 'avg rsrp',
          version: 1,
          upstream: [],
        },
        {
          id: 'f-up-2',
          name: 'hour_bucket',
          field_type: 'TIMESTAMP',
          is_nullable: false,
          is_partition: true,
          expression: null,
          description: 'hour',
          version: 1,
          upstream: [],
        },
      ],
    },
    {
      id: 't-down',
      name: 'ads_cell_profile',
      layer: 'ADS',
      layer_priority: 4,
      storage_type: 'STARROCKS',
      description: 'profile',
      field_count: 1,
      sql_logic: null,
      sql_dialect: null,
      sql_source: null,
      sql_updated_at: '',
      fields: [
        {
          id: 'f-down-1',
          name: 'coverage_score',
          field_type: 'DOUBLE',
          is_nullable: true,
          is_partition: false,
          expression: 'weighted(avg_rsrp)',
          description: 'coverage',
          version: 1,
          upstream: [],
        },
      ],
    },
  ],
  table_edges: [
    {
      source: 'dwd_session_qos',
      target: 'dws_cell_hourly',
      direction: 'upstream',
      field_edge_count: 1,
      calc_type_counts: { AGGREGATE: 1 },
      fields: ['avg_rsrp'],
    },
    {
      source: 'dws_cell_hourly',
      target: 'ads_cell_profile',
      direction: 'downstream',
      field_edge_count: 1,
      calc_type_counts: { DIRECT: 1 },
      fields: ['coverage_score'],
    },
  ],
  field_edges: [
    {
      edge_id: 'edge-1',
      from_table: 'dwd_session_qos',
      from_field: 'avg_rsrp',
      to_table: 'dws_cell_hourly',
      to_field: 'avg_rsrp',
      transform_expr: 'AVG(q.avg_rsrp)',
      calc_type: 'AGGREGATE',
      calc_params: { function: 'AVG' },
    },
    {
      edge_id: 'edge-2',
      from_table: 'dws_cell_hourly',
      from_field: 'avg_rsrp',
      to_table: 'ads_cell_profile',
      to_field: 'coverage_score',
      transform_expr: 'weighted(avg_rsrp)',
      calc_type: 'DIRECT',
      calc_params: {},
    },
  ],
}

describe('lineageX6Adapter', () => {
  test('builds deterministic table nodes around the root table', () => {
    const graph = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(),
      selectedEdgeKey: undefined,
    })

    const root = graph.nodes.find((node) => node.id === 'dws_cell_hourly')
    const upstream = graph.nodes.find((node) => node.id === 'dwd_session_qos')
    const downstream = graph.nodes.find((node) => node.id === 'ads_cell_profile')

    expect(root?.x).toBe(520)
    expect(upstream?.x).toBeLessThan(root?.x ?? 0)
    expect(downstream?.x).toBeGreaterThan(root?.x ?? 0)
    expect(graph.edges.map((edge) => edge.id)).toContain(tableEdgeCellId('dwd_session_qos', 'dws_cell_hourly'))
  })

  test('expanded tables expose stable field ports and dashed field edges', () => {
    const graph = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(['dwd_session_qos', 'dws_cell_hourly']),
      selectedEdgeKey: edgeKey(payload.field_edges[0]),
    })

    const upstream = graph.nodes.find((node) => node.id === 'dwd_session_qos')
    const root = graph.nodes.find((node) => node.id === 'dws_cell_hourly')
    const fieldEdge = graph.edges.find((item) => item.id === fieldEdgeCellId(payload.field_edges[0]))

    expect(upstream?.ports?.items?.map((port) => port.id)).toContain(fieldPortId('out', 'avg_rsrp'))
    expect(root?.ports?.items?.map((port) => port.id)).toContain(fieldPortId('in', 'avg_rsrp'))
    expect(fieldEdge?.source).toEqual({ cell: 'dwd_session_qos', port: fieldPortId('out', 'avg_rsrp') })
    expect(fieldEdge?.target).toEqual({ cell: 'dws_cell_hourly', port: fieldPortId('in', 'avg_rsrp') })
    expect(fieldEdge?.attrs?.line?.strokeDasharray).toBe('5 5')
    expect(fieldEdge?.attrs?.line?.stroke).toBe('#2563eb')
  })

  test('field-level edges are hidden until a related table is expanded', () => {
    const collapsed = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(),
      selectedEdgeKey: undefined,
    })

    const expanded = buildLineageX6GraphData({
      payload,
      expandedTables: new Set(['dws_cell_hourly']),
      selectedEdgeKey: undefined,
    })

    expect(collapsed.edges.some((item) => item.id === fieldEdgeCellId(payload.field_edges[0]))).toBe(false)
    expect(expanded.edges.some((item) => item.id === fieldEdgeCellId(payload.field_edges[0]))).toBe(true)
  })
})
```

- [ ] **Step 2: Run adapter tests and verify failure**

Run:

```powershell
npm.cmd --prefix frontend run test:unit -- src/components/graphShared/lineageX6Adapter.test.ts
```

Expected: fail because `lineageX6Adapter.ts` does not exist.

- [ ] **Step 3: Implement adapter**

Create `frontend/src/components/graphShared/lineageX6Adapter.ts`:

```ts
import type { Edge, Node } from '@antv/x6'
import type { LineageEdge, LineageGraphResponse, LineageTableNode } from '../../api/client'
import { colorForLayer } from './palette'

export type LineageX6GraphInput = {
  payload?: LineageGraphResponse
  expandedTables: Set<string>
  selectedEdgeKey?: string
}

export type LineageX6GraphData = {
  nodes: Node.Metadata[]
  edges: Edge.Metadata[]
  fieldEdgeByCellId: Map<string, LineageEdge>
}

const NODE_WIDTH = 238
const COLLAPSED_HEIGHT = 76
const HEADER_HEIGHT = 48
const FIELD_ROW_HEIGHT = 28
const FIELD_TOP = 58
const CENTER_X = 520
const CENTER_Y = 260
const COLUMN_GAP = 320
const ROW_GAP = 190

type TablePosition = {
  x: number
  y: number
  side: 'upstream' | 'root' | 'downstream'
  level: number
}

export function edgeKey(edge: LineageEdge) {
  return edge.edge_id || `${edge.from_table}.${edge.from_field}->${edge.to_table}.${edge.to_field}`
}

export function safeCellId(value: string) {
  return value.replace(/[^a-zA-Z0-9_-]/g, '_')
}

export function tableEdgeCellId(source: string, target: string) {
  return `table-edge-${safeCellId(`${source}-${target}`)}`
}

export function fieldEdgeCellId(edge: LineageEdge) {
  return `field-edge-${safeCellId(edgeKey(edge))}`
}

export function fieldPortId(direction: 'in' | 'out', field: string) {
  return `${direction}:${field}`
}

function nodeHeight(table: LineageTableNode, expanded: boolean) {
  return expanded ? FIELD_TOP + table.fields.length * FIELD_ROW_HEIGHT + 14 : COLLAPSED_HEIGHT
}

function visibleFieldY(index: number, expanded: boolean) {
  return expanded ? FIELD_TOP + index * FIELD_ROW_HEIGHT + FIELD_ROW_HEIGHT / 2 : HEADER_HEIGHT + 14
}

function connectedTableNames(payload: LineageGraphResponse) {
  const names = new Set([payload.root_table])
  payload.table_edges.forEach((edge) => {
    names.add(edge.source)
    names.add(edge.target)
  })
  return names
}

function tableLevel(payload: LineageGraphResponse, tableName: string, side: 'upstream' | 'downstream') {
  if (tableName === payload.root_table) return 0
  let frontier = new Set([payload.root_table])
  const seen = new Set(frontier)
  for (let depth = 1; depth <= payload.depth; depth += 1) {
    const next = new Set<string>()
    payload.table_edges.forEach((edge) => {
      if (side === 'upstream' && frontier.has(edge.target) && !seen.has(edge.source)) next.add(edge.source)
      if (side === 'downstream' && frontier.has(edge.source) && !seen.has(edge.target)) next.add(edge.target)
    })
    if (next.has(tableName)) return depth
    next.forEach((name) => seen.add(name))
    frontier = next
  }
  return 1
}

function buildPositions(payload: LineageGraphResponse) {
  const visible = connectedTableNames(payload)
  const upstream = payload.tables
    .filter((table) => table.name !== payload.root_table && visible.has(table.name))
    .filter((table) => payload.table_edges.some((edge) => edge.source === table.name && edge.direction === 'upstream'))
    .sort((a, b) => a.layer_priority - b.layer_priority || a.name.localeCompare(b.name))
  const downstream = payload.tables
    .filter((table) => table.name !== payload.root_table && visible.has(table.name))
    .filter((table) => payload.table_edges.some((edge) => edge.target === table.name && edge.direction === 'downstream'))
    .sort((a, b) => a.layer_priority - b.layer_priority || a.name.localeCompare(b.name))
  const positions = new Map<string, TablePosition>()
  positions.set(payload.root_table, { x: CENTER_X, y: CENTER_Y, side: 'root', level: 0 })

  upstream.forEach((table, index) => {
    const level = tableLevel(payload, table.name, 'upstream')
    positions.set(table.name, {
      x: CENTER_X - level * COLUMN_GAP,
      y: CENTER_Y + (index - (upstream.length - 1) / 2) * ROW_GAP,
      side: 'upstream',
      level,
    })
  })

  downstream.forEach((table, index) => {
    const level = tableLevel(payload, table.name, 'downstream')
    positions.set(table.name, {
      x: CENTER_X + level * COLUMN_GAP,
      y: CENTER_Y + (index - (downstream.length - 1) / 2) * ROW_GAP,
      side: 'downstream',
      level,
    })
  })

  return positions
}

function buildTableNode(table: LineageTableNode, position: TablePosition, rootTable: string, expanded: boolean): Node.Metadata {
  const palette = colorForLayer(table.layer)
  const height = nodeHeight(table, expanded)
  const markup: Node.Markup[] = [
    { tagName: 'rect', selector: 'body' },
    { tagName: 'rect', selector: 'header' },
    { tagName: 'text', selector: 'title' },
    { tagName: 'text', selector: 'meta' },
    { tagName: 'rect', selector: 'toggleButton' },
    { tagName: 'text', selector: 'toggleLabel' },
  ]
  const attrs: Node.Metadata['attrs'] = {
    body: {
      width: NODE_WIDTH,
      height,
      rx: 8,
      ry: 8,
      fill: '#ffffff',
      stroke: table.name === rootTable ? '#2563eb' : palette.stroke,
      strokeWidth: table.name === rootTable ? 2 : 1,
      filter: table.name === rootTable ? 'drop-shadow(0 4px 12px rgba(37,99,235,0.18))' : undefined,
    },
    header: {
      width: NODE_WIDTH,
      height: HEADER_HEIGHT,
      rx: 8,
      ry: 8,
      fill: palette.fill,
      stroke: palette.stroke,
      strokeWidth: 1,
    },
    title: {
      x: 14,
      y: 22,
      text: table.name,
      fontSize: 13,
      fontWeight: 700,
      fill: '#172033',
    },
    meta: {
      x: 14,
      y: 40,
      text: `${table.layer} / ${table.storage_type} / ${table.field_count} fields`,
      fontSize: 10,
      fill: '#64748b',
    },
    toggleButton: {
      x: NODE_WIDTH - 34,
      y: 12,
      width: 22,
      height: 22,
      rx: 5,
      ry: 5,
      fill: '#ffffff',
      stroke: '#94a3b8',
      cursor: 'pointer',
      event: 'lineage:toggle-table',
    },
    toggleLabel: {
      x: NODE_WIDTH - 23,
      y: 28,
      text: expanded ? '-' : '+',
      textAnchor: 'middle',
      fontSize: 16,
      fontWeight: 700,
      fill: '#334155',
      cursor: 'pointer',
      event: 'lineage:toggle-table',
    },
  }

  if (expanded) {
    table.fields.forEach((field, index) => {
      const rowY = FIELD_TOP + index * FIELD_ROW_HEIGHT
      const row = `fieldRow${index}`
      const name = `fieldName${index}`
      const type = `fieldType${index}`
      markup.push({ tagName: 'rect', selector: row })
      markup.push({ tagName: 'text', selector: name })
      markup.push({ tagName: 'text', selector: type })
      attrs[row] = {
        x: 12,
        y: rowY,
        width: NODE_WIDTH - 24,
        height: FIELD_ROW_HEIGHT - 6,
        rx: 5,
        ry: 5,
        fill: '#f8fafc',
        stroke: '#e2e8f0',
      }
      attrs[name] = {
        x: 30,
        y: rowY + 15,
        text: field.name,
        fontSize: 11,
        fill: '#172033',
      }
      attrs[type] = {
        x: NODE_WIDTH - 82,
        y: rowY + 15,
        text: field.field_type,
        fontSize: 10,
        fill: '#64748b',
      }
    })
  }

  return {
    id: table.name,
    shape: 'lineage-table',
    x: position.x,
    y: position.y,
    width: NODE_WIDTH,
    height,
    markup,
    attrs,
    data: { kind: 'table', table, expanded },
    ports: {
      groups: {
        in: {
          position: { name: 'absolute' },
          attrs: { circle: { r: 5, magnet: true, stroke: '#2563eb', strokeWidth: 2, fill: '#ffffff' } },
        },
        out: {
          position: { name: 'absolute' },
          attrs: { circle: { r: 5, magnet: true, stroke: '#16a34a', strokeWidth: 2, fill: '#ffffff' } },
        },
      },
      items: table.fields.flatMap((field, index) => {
        const y = visibleFieldY(index, expanded)
        return [
          { id: fieldPortId('in', field.name), group: 'in', args: { x: 0, y } },
          { id: fieldPortId('out', field.name), group: 'out', args: { x: NODE_WIDTH, y } },
        ]
      }),
    },
  }
}

export function buildLineageX6GraphData({ payload, expandedTables, selectedEdgeKey }: LineageX6GraphInput): LineageX6GraphData {
  if (!payload) return { nodes: [], edges: [], fieldEdgeByCellId: new Map() }

  const positions = buildPositions(payload)
  const visibleNames = new Set(payload.tables.map((table) => table.name))
  const nodes = payload.tables
    .filter((table) => visibleNames.has(table.name))
    .map((table) => buildTableNode(
      table,
      positions.get(table.name) ?? { x: CENTER_X, y: CENTER_Y, side: 'root', level: 0 },
      payload.root_table,
      expandedTables.has(table.name),
    ))

  const tableEdges: Edge.Metadata[] = payload.table_edges.map((edge) => ({
    id: tableEdgeCellId(edge.source, edge.target),
    shape: 'edge',
    source: { cell: edge.source },
    target: { cell: edge.target },
    connector: { name: 'smooth' },
    attrs: {
      line: {
        stroke: edge.direction === 'upstream' ? '#64748b' : '#16a34a',
        strokeWidth: 2,
        targetMarker: { name: 'block', width: 9, height: 7 },
      },
    },
    labels: [{ attrs: { label: { text: `${edge.field_edge_count} fields`, fontSize: 10, fill: '#475569' } } }],
    data: { kind: 'table-edge', edge },
  }))

  const fieldEdgeByCellId = new Map<string, LineageEdge>()
  const fieldEdges: Edge.Metadata[] = payload.field_edges
    .filter((edge) => expandedTables.has(edge.from_table) || expandedTables.has(edge.to_table))
    .map((edge) => {
      const id = fieldEdgeCellId(edge)
      fieldEdgeByCellId.set(id, edge)
      const selected = selectedEdgeKey === edgeKey(edge)
      return {
        id,
        shape: 'edge',
        source: { cell: edge.from_table, port: fieldPortId('out', edge.from_field) },
        target: { cell: edge.to_table, port: fieldPortId('in', edge.to_field) },
        connector: { name: 'smooth' },
        attrs: {
          line: {
            stroke: selected ? '#2563eb' : '#94a3b8',
            strokeWidth: selected ? 2.6 : 1.6,
            strokeDasharray: '5 5',
            opacity: selected ? 1 : 0.72,
            targetMarker: { name: 'block', width: 8, height: 6 },
          },
        },
        data: { kind: 'field-edge', lineageEdgeKey: edgeKey(edge), edge },
      } satisfies Edge.Metadata
    })

  return { nodes, edges: [...tableEdges, ...fieldEdges], fieldEdgeByCellId }
}
```

- [ ] **Step 4: Run unit tests and commit**

Run:

```powershell
npm.cmd --prefix frontend run test:unit -- src/components/graphShared/lineageX6Adapter.test.ts
npm.cmd --prefix frontend run lint
```

Expected: adapter tests pass and lint passes.

Commit:

```powershell
git add frontend/src/components/graphShared/lineageX6Adapter.ts frontend/src/components/graphShared/lineageX6Adapter.test.ts
git commit -m "ui: add lineage x6 graph adapter"
```

## Task 3: Render X6 Canvas With Table Nodes And Curved Table Edges

**Files:**
- Modify: `frontend/src/components/LineageWorkspaceGraph.tsx`
- Modify: `frontend/src/pages/Lineage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/e2e/lineage.spec.ts`

- [ ] **Step 1: Add failing X6 canvas e2e assertions**

In `frontend/tests/e2e/lineage.spec.ts`, update the first test after `await page.goto('/metadata/lineage?table=dws_cell_hourly')`:

```ts
  await expect(page.locator('.lineage-x6-canvas .x6-graph')).toBeVisible()
  await expect(page.locator('.lineage-x6-canvas')).toContainText('dws_cell_hourly')
  await expect(page.locator('.lineage-x6-canvas')).toContainText('dwd_session_qos')
  await expect(page.locator('[data-cell-id^="table-edge-"]').first()).toBeVisible()
```

Keep the existing checkbox assertions. Replace DOM-list specific assertions only after X6 equivalents exist.

- [ ] **Step 2: Run e2e and verify failure**

Run:

```powershell
npm.cmd --prefix frontend run test:e2e -- tests/e2e/lineage.spec.ts
```

Expected: fail because `.lineage-x6-canvas .x6-graph` does not exist.

If this local machine still has an unrelated service on `127.0.0.1:5173`, use this temporary config outside version control for real validation:

```ts
// frontend/playwright.lineage-temp.config.ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'on-first-retry',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5174 --strictPort',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
```

Then run:

```powershell
npm.cmd --prefix frontend exec -- playwright test --config=frontend/playwright.lineage-temp.config.ts tests/e2e/lineage.spec.ts
```

Remove `frontend/playwright.lineage-temp.config.ts` and `frontend/test-results/` after validation.

- [ ] **Step 3: Replace graph component with X6 shell**

Replace `frontend/src/components/LineageWorkspaceGraph.tsx` with:

```tsx
import { Empty, Tooltip } from 'antd'
import { Graph } from '@antv/x6'
import { MiniMap } from '@antv/x6-plugin-minimap'
import '@antv/x6/dist/index.css'
import '@antv/x6-plugin-minimap/dist/index.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { LineageEdge, LineageGraphResponse } from '../api/client'
import GraphToolbar from './GraphToolbar'
import { buildLineageX6GraphData, edgeKey } from './graphShared/lineageX6Adapter'

type EdgeEndpoint = 'from' | 'to'

type Props = {
  payload?: LineageGraphResponse
  expandedTables: Set<string>
  selectedEdge?: LineageEdge
  onToggleTable: (table: string) => void
  onSelectFieldEdge: (edge: LineageEdge) => void
  onMoveEdgeEndpoint: (edge: LineageEdge, endpoint: EdgeEndpoint, table: string, field: string) => void
}

type TooltipState = {
  visible: boolean
  x: number
  y: number
  text: string
}

function portToField(port?: string) {
  const parts = (port ?? '').split(':')
  return parts.length === 2 ? parts[1] : undefined
}

export default function LineageWorkspaceGraph({
  payload,
  expandedTables,
  selectedEdge,
  onToggleTable,
  onSelectFieldEdge,
  onMoveEdgeEndpoint,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const minimapRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<Graph>()
  const [tooltip, setTooltip] = useState<TooltipState>({ visible: false, x: 0, y: 0, text: '' })
  const [pendingMove, setPendingMove] = useState<{ edge: LineageEdge; endpoint: EdgeEndpoint }>()
  const selectedEdgeKey = selectedEdge ? edgeKey(selectedEdge) : undefined

  const graphData = useMemo(
    () => buildLineageX6GraphData({ payload, expandedTables, selectedEdgeKey }),
    [payload, expandedTables, selectedEdgeKey],
  )

  useEffect(() => {
    if (!containerRef.current || graphRef.current) return
    const graph = new Graph({
      container: containerRef.current,
      autoResize: true,
      background: { color: '#f8fafc' },
      grid: { visible: true, type: 'dot', args: { color: '#dbe3ef', thickness: 1 } },
      panning: { enabled: true },
      mousewheel: { enabled: true, modifiers: ['ctrl', 'meta'], minScale: 0.35, maxScale: 1.8 },
      connecting: {
        allowBlank: false,
        allowLoop: false,
        allowNode: false,
        allowEdge: false,
        snap: true,
        validateConnection({ sourceMagnet, targetMagnet }) {
          return Boolean(sourceMagnet && targetMagnet)
        },
      },
    })
    graph.use(new MiniMap({ container: minimapRef.current ?? undefined, width: 180, height: 116 }))
    graphRef.current = graph

    graph.on('lineage:toggle-table', ({ cell }) => {
      const table = cell?.id
      if (typeof table === 'string') onToggleTable(table)
    })

    graph.on('edge:click', ({ edge }) => {
      const data = edge.getData() as { kind?: string; edge?: LineageEdge }
      if (data.kind === 'field-edge' && data.edge) onSelectFieldEdge(data.edge)
    })

    graph.on('edge:mouseenter', ({ e, edge }) => {
      const data = edge.getData() as { kind?: string; edge?: LineageEdge }
      if (data.kind !== 'field-edge' || !data.edge) return
      setTooltip({
        visible: true,
        x: e.clientX + 12,
        y: e.clientY + 12,
        text: `${data.edge.from_table}.${data.edge.from_field} -> ${data.edge.to_table}.${data.edge.to_field} | ${data.edge.calc_type ?? 'DIRECT'} | ${data.edge.transform_expr}`,
      })
    })

    graph.on('edge:mousemove', ({ e }) => {
      setTooltip((prev) => (prev.visible ? { ...prev, x: e.clientX + 12, y: e.clientY + 12 } : prev))
    })

    graph.on('edge:mouseleave', () => {
      setTooltip((prev) => ({ ...prev, visible: false }))
    })

    graph.on('edge:connected', ({ edge, isNew }) => {
      if (isNew) {
        edge.remove()
        return
      }
      const data = edge.getData() as { kind?: string; edge?: LineageEdge }
      if (data.kind !== 'field-edge' || !data.edge) return
      const source = edge.getSource() as { cell?: string; port?: string }
      const target = edge.getTarget() as { cell?: string; port?: string }
      const sourceField = portToField(source.port)
      const targetField = portToField(target.port)
      if (source.cell && sourceField && source.cell !== data.edge.from_table) {
        onMoveEdgeEndpoint(data.edge, 'from', source.cell, sourceField)
        return
      }
      if (source.cell && sourceField && sourceField !== data.edge.from_field) {
        onMoveEdgeEndpoint(data.edge, 'from', source.cell, sourceField)
        return
      }
      if (target.cell && targetField && target.cell !== data.edge.to_table) {
        onMoveEdgeEndpoint(data.edge, 'to', target.cell, targetField)
        return
      }
      if (target.cell && targetField && targetField !== data.edge.to_field) {
        onMoveEdgeEndpoint(data.edge, 'to', target.cell, targetField)
      }
    })

    return () => {
      graph.dispose()
      graphRef.current = undefined
    }
  }, [onMoveEdgeEndpoint, onSelectFieldEdge, onToggleTable])

  useEffect(() => {
    const graph = graphRef.current
    if (!graph) return
    graph.resetCells([...graphData.nodes, ...graphData.edges])
    window.setTimeout(() => graph.centerContent(), 0)
  }, [graphData])

  if (!payload || graphData.nodes.length === 0) {
    return <Empty className="lineage-workspace-graph" description="暂无血缘工作区数据" />
  }

  return (
    <div className="lineage-workspace-graph lineage-x6-shell">
      <GraphToolbar
        onFit={() => graphRef.current?.zoomToFit({ padding: 32, maxScale: 1 })}
        onFullscreen={() => containerRef.current?.requestFullscreen?.()}
      />
      <div className="lineage-x6-canvas" ref={containerRef} />
      <div className="lineage-x6-minimap" ref={minimapRef} />
      <Tooltip open={tooltip.visible} title={tooltip.text} placement="right">
        <span className="lineage-x6-tooltip-anchor" style={{ left: tooltip.x, top: tooltip.y }} />
      </Tooltip>
      <div className="lineage-x6-accessible" aria-label="lineage graph accessibility controls">
        {(payload.field_edges ?? []).map((edge) => (
          <div key={edgeKey(edge)}>
            <button type="button" aria-label={`field edge ${edgeKey(edge)}`} onClick={() => onSelectFieldEdge(edge)} />
            <button type="button" aria-label={`source endpoint ${edgeKey(edge)}`} onClick={() => setPendingMove({ edge, endpoint: 'from' })} />
            <button type="button" aria-label={`target endpoint ${edgeKey(edge)}`} onClick={() => setPendingMove({ edge, endpoint: 'to' })} />
          </div>
        ))}
        {(payload.tables ?? []).flatMap((table) =>
          table.fields.map((field) => (
            <button
              key={`${table.name}.${field.name}`}
              type="button"
              aria-label={`field port ${table.name}.${field.name}`}
              onClick={() => {
                if (!pendingMove) return
                onMoveEdgeEndpoint(pendingMove.edge, pendingMove.endpoint, table.name, field.name)
                setPendingMove(undefined)
              }}
            />
          )),
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Pass selected edge from the page**

In `frontend/src/pages/Lineage.tsx`, update the `LineageWorkspaceGraph` usage:

```tsx
        <LineageWorkspaceGraph
          payload={workspacePayload}
          expandedTables={expandedTables}
          selectedEdge={edge}
          onToggleTable={toggleTable}
          onSelectFieldEdge={(next) => {
            setEdge(next)
            setNodeId(undefined)
          }}
          onMoveEdgeEndpoint={moveEndpoint}
        />
```

- [ ] **Step 5: Replace graph styles**

In `frontend/src/styles.css`, replace the existing `.lineage-workspace-graph`, `.lineage-table-edge-layer`, `.lineage-table-edge`, `.lineage-table-grid`, `.lineage-table-node`, `.lineage-field-edge-list`, `.lineage-field-edge-row`, `.lineage-field-edge-select`, `.lineage-field-row`, and `.lineage-anchor` blocks with:

```css
.lineage-workspace-graph.lineage-x6-shell {
  position: relative;
  min-height: calc(100vh - 136px);
  height: calc(100vh - 136px);
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #f8fafc;
}

.lineage-x6-canvas {
  width: 100%;
  height: 100%;
}

.lineage-x6-minimap {
  position: absolute;
  right: 12px;
  bottom: 12px;
  width: 180px;
  height: 116px;
  overflow: hidden;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.92);
}

.lineage-x6-tooltip-anchor {
  position: fixed;
  width: 1px;
  height: 1px;
  pointer-events: none;
}

.lineage-x6-accessible {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.x6-edge-selected path:nth-child(2),
.x6-edge:hover path:nth-child(2) {
  stroke-width: 3px;
}
```

- [ ] **Step 6: Run checks and commit**

Run:

```powershell
npm.cmd --prefix frontend run test:unit -- src/components/graphShared/lineageX6Adapter.test.ts
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Expected: unit tests, lint, and build pass. Vite may warn about large chunks.

Run lineage e2e using the standard config or the 5174 temporary config described in Step 2:

```powershell
npm.cmd --prefix frontend run test:e2e -- tests/e2e/lineage.spec.ts
```

Expected: lineage e2e passes or fails only due the known local 5173 port reuse issue. If 5173 is occupied, validate with 5174 and remove the temporary config and `frontend/test-results/`.

Commit:

```powershell
git add frontend/src/components/LineageWorkspaceGraph.tsx frontend/src/pages/Lineage.tsx frontend/src/styles.css frontend/tests/e2e/lineage.spec.ts
git commit -m "ui: render lineage workspace with x6"
```

## Task 4: Field Expansion, Edge Selection, And Endpoint Reconnection Coverage

**Files:**
- Modify: `frontend/tests/e2e/lineage.spec.ts`
- Modify: `frontend/src/components/LineageWorkspaceGraph.tsx` only if Task 3 e2e identifies gaps in event wiring.

- [ ] **Step 1: Update expansion and direction e2e to assert X6 behavior**

In the first lineage e2e test, replace DOM row assertions with:

```ts
  await page.locator('.lineage-x6-canvas').getByText('dws_cell_hourly').click()
  await page.locator('.lineage-x6-canvas').getByText('+').first().click()
  await expect(page.locator('.lineage-x6-canvas')).toContainText('avg_rsrp')
  await expect(page.locator('[data-cell-id^="field-edge-"]').first()).toBeVisible()

  await page.getByRole('checkbox', { name: '后向' }).uncheck()
  await expect(page.locator('.lineage-x6-canvas')).not.toContainText('dwd_session_qos')
```

If the current test file still uses mojibake labels from earlier encoding, keep the existing checkbox label selectors and only replace graph-specific selectors:

```ts
  await page.getByRole('checkbox', { name: '鍙嶅悜' }).uncheck()
```

- [ ] **Step 2: Update edge selection e2e**

Replace the edge selection action in `lineage workspace selects field edges from the keyboard` with:

```ts
  await page.getByRole('button', { name: 'field edge edge-1' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText('AVG(q.avg_rsrp)').last()).toBeVisible()
```

Expected: keyboard selection uses the hidden semantic control and right panel shows the selected field edge.

- [ ] **Step 3: Update endpoint movement e2e**

Replace source endpoint keyboard movement actions with:

```ts
  await page.getByRole('button', { name: 'source endpoint edge-1' }).press('Enter')
  await page.getByRole('button', { name: 'field port dwd_session_qos.hour_bucket' }).press('Enter')
```

Keep the existing expected PATCH payload:

```ts
  await expect.poll(() => patchBody).toEqual({
    from_table: 'dwd_session_qos',
    from_field: 'hour_bucket',
    to_table: 'dws_cell_hourly',
    to_field: 'avg_rsrp',
  })
```

- [ ] **Step 4: Add visible X6 edge click test**

Append this e2e test:

```ts
test('lineage x6 field edge click loads the edge editor', async ({ page }) => {
  await mockCommonApis(page)

  await page.goto('/metadata/lineage?table=dws_cell_hourly')
  await page.locator('.lineage-x6-canvas').getByText('+').first().click()
  await page.locator('[data-cell-id="field-edge-edge-1"]').click()

  await expect(page.getByRole('heading', { name: '边计算配置' })).toBeVisible()
  await expect(page.getByText('dwd_session_qos.avg_rsrp')).toBeVisible()
})
```

If existing rendered text is mojibake in the current test environment, assert stable data instead:

```ts
  await expect(page.getByText('dwd_session_qos.avg_rsrp')).toBeVisible()
```

- [ ] **Step 5: Run lineage e2e and commit**

Run:

```powershell
npm.cmd --prefix frontend run test:e2e -- tests/e2e/lineage.spec.ts
npm.cmd --prefix frontend run lint
```

Expected: lineage e2e and lint pass. Use the 5174 temporary Playwright config if the local 5173 conflict is still present.

Commit:

```powershell
git add frontend/tests/e2e/lineage.spec.ts frontend/src/components/LineageWorkspaceGraph.tsx
git commit -m "test: cover x6 lineage interactions"
```

## Task 5: Final Verification, Visual QA, And Documentation Check

**Files:**
- Modify: `docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md` only if implementation differs from the confirmed X6 design.

- [ ] **Step 1: Run backend regression tests**

Run:

```powershell
$env:YARN_RM_URL='http://resourcemanager:8088'; $env:HDFS_DEFAULTFS='hdfs://namenode:8020'; $env:HIVE_METASTORE_URI='thrift://hive-metastore:9083'; python -m pytest -m "not infra"
```

Expected: all selected backend tests pass.

- [ ] **Step 2: Run frontend checks**

Run:

```powershell
npm.cmd --prefix frontend run test:unit
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Expected: unit tests, lint, and build pass. Vite large chunk warning is acceptable.

- [ ] **Step 3: Run full frontend e2e**

Run:

```powershell
npm.cmd --prefix frontend run test:e2e
```

Expected: all e2e tests pass when the standard 5173 dev server is available.

If the machine still has an unrelated service occupying `127.0.0.1:5173`, validate with the 5174 temporary config from Task 3 Step 2:

```powershell
npm.cmd --prefix frontend exec -- playwright test --config=frontend/playwright.lineage-temp.config.ts
```

Expected: all e2e tests pass on 5174. After the run, delete the temporary config with `apply_patch` and remove generated `frontend/test-results/` after verifying the resolved path is under the repo root.

- [ ] **Step 4: Manual rendered check**

Start the app if it is not already running:

```powershell
Start-Process -FilePath 'npm.cmd' -ArgumentList @('--prefix','frontend','run','dev','--','--host','127.0.0.1','--port','5174','--strictPort') -WorkingDirectory 'D:\agent-code\data-gov' -WindowStyle Hidden
Start-Process 'http://127.0.0.1:5174/metadata/lineage?table=dws_cell_hourly'
```

Check these visual states:

- The center panel is an X6 canvas with visible table cards and curved table-level edges.
- The target table is centered and visually emphasized.
- Expanding `dws_cell_hourly` reveals field rows inside the node.
- A dashed field-level edge appears when a related table is expanded.
- Hovering a field edge shows source field, target field, calculation type, and expression.
- Clicking a field edge loads the right-side edge editor.
- Dragging or keyboard-moving an endpoint triggers the existing endpoint PATCH and refreshes SQL preview.

- [ ] **Step 5: Documentation check**

Run:

```powershell
git diff -- docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md
rg -n "血缘工作台.*G6|LineageGraph\\.tsx|共享 G6" docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md
```

Expected: no design drift and no stale statement saying `/metadata/lineage` uses G6. If implementation behavior differs from the spec, update the spec with the actual behavior and commit:

```powershell
git add docs/superpowers/specs/2026-05-13-wireless-rno-data-service-design.md
git commit -m "docs: align x6 lineage workspace behavior"
```

- [ ] **Step 6: Final status check**

Run:

```powershell
git status --short --branch
git log --oneline -10
```

Expected: working tree clean, with the X6 implementation commits visible at the top of the log.

## Self-Review Checklist

- Spec coverage:
  - X6 editable lineage workspace: Tasks 1, 2, 3.
  - Table-level first rendering with curved edges: Tasks 2, 3.
  - Forward/backward visibility controls: Task 4 e2e keeps existing `Lineage.tsx` filter behavior and verifies X6 output.
  - Expandable table fields inside nodes: Tasks 2, 3, 4.
  - Field ports and dashed field-level edges: Tasks 2, 3, 4.
  - Edge hover and click to right-side editor: Tasks 3, 4.
  - Endpoint reconnection and immediate save: Tasks 3, 4.
  - SQL preview refresh after graph edit: existing `Lineage.tsx` mutation wiring remains, verified in Task 4 and Task 5.
  - `/pipeline` remains G6 and read-only: Scope Boundaries, no pipeline file changes.
- Placeholder scan: no placeholder markers remain in this plan; every file path and command is concrete.
- Type consistency:
  - `LineageGraphResponse`, `LineageEdge`, `LineageTableNode`, `edge_id`, `calc_type`, and `calc_params` match `frontend/src/api/client.ts`.
  - `onMoveEdgeEndpoint(edge, endpoint, table, field)` matches existing `LineageWorkspaceGraph` props.
  - `fieldPortId('in' | 'out', field)` is used consistently in adapter tests and X6 cell metadata.
