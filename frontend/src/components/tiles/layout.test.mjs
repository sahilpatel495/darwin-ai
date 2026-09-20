// Run: cd frontend && node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { kpiLabel, kpiValue, packTiles, tileSpan } from './layout.ts'
import dashboard from '../../fixtures/dashboard.json' with { type: 'json' }

const tile = (over) => ({ kind: 'breakdown', chart: null, table: null, ...over })
const chart = (over) => ({ type: 'bar', x: 'department', y: ['employees'], series: null, title: '', note: null, value_format: 'number', ...over })

test('a single figure takes a quarter of the row', () => {
  assert.equal(tileSpan(tile({ kind: 'kpi', chart: chart({ type: 'kpi' }) })), 'kpi')
  // A template that sends a kpi chart under another kind is still one figure.
  assert.equal(tileSpan(tile({ kind: 'metric', chart: chart({ type: 'kpi' }) })), 'kpi')
})

test('an ordinary chart takes half the row', () => {
  assert.equal(tileSpan(tile({ kind: 'breakdown', chart: chart() })), 'half')
  assert.equal(tileSpan(tile({ kind: 'trend', chart: chart({ type: 'area' }) })), 'half')
  assert.equal(tileSpan(tile({ kind: 'distribution', chart: chart({ type: 'histogram' }) })), 'half')
  assert.equal(tileSpan(tile({ kind: 'share', chart: chart({ type: 'donut' }) })), 'half')
})

test('two categories in one chart take the whole width', () => {
  assert.equal(tileSpan(tile({ kind: 'comparison', chart: chart({ type: 'stacked_bar', series: 'location' }) })), 'full')
  assert.equal(tileSpan(tile({ kind: 'relationship', chart: chart({ type: 'heatmap', series: 'rating' }) })), 'full')
  // Either signal alone is enough: the kind without a series, and a series under any kind.
  assert.equal(tileSpan(tile({ kind: 'comparison', chart: chart() })), 'full')
  assert.equal(tileSpan(tile({ kind: 'breakdown', chart: chart({ series: 'location' }) })), 'full')
})

test('the data quality checklist takes the whole width and has no chart', () => {
  assert.equal(tileSpan(tile({ kind: 'quality', chart: null })), 'full')
})

test('the fixture dashboard lays out as §13 describes', () => {
  const spans = dashboard.sections.flatMap((section) => section.tiles.map((t) => [t.id, tileSpan(t)]))
  assert.deepEqual(Object.fromEntries(spans), {
    'kpi-headcount': 'kpi',
    'break-dept': 'half',
    'share-gender': 'half',
    'stack-loc': 'full',
    'kpi-pay': 'kpi',
    'trend-pay': 'half',
    'dist-ctc': 'half',
    'heat-rating': 'full',
    quality: 'full',
  })
})

test('a KPI tile shows the display string of the column its chart names', () => {
  const table = { columns: ['headcount', 'active_employees'], rows: [[999, 430]], display: [['999', '430']], row_count: 1, truncated: false }
  assert.equal(kpiValue({ chart: chart({ type: 'kpi', y: ['active_employees'] }), table }), '430')
  // No usable column name: the first column is the figure.
  assert.equal(kpiValue({ chart: chart({ type: 'kpi', y: ['gone'] }), table }), '999')
  assert.equal(kpiValue({ chart: null, table }), '999')
})

test('a KPI tile with no rows has no figure to show', () => {
  assert.equal(kpiValue({ chart: null, table: null }), null)
  assert.equal(kpiValue({ chart: null, table: { columns: ['n'], rows: [], display: [], row_count: 0, truncated: false } }), null)
})

test('the fixture KPI tiles read as their statements do', () => {
  const tiles = Object.fromEntries(dashboard.sections.flatMap((s) => s.tiles.map((t) => [t.id, t])))
  assert.equal(kpiValue(tiles['kpi-headcount']), '430')
  assert.equal(kpiValue(tiles['kpi-pay']), '₹54.67 Cr')
})

test('a KPI sentence that only repeats the title and the figure is not printed under it', () => {
  assert.equal(kpiLabel({ title: 'Active headcount', statement: 'Active headcount is 430.' }, '430'), undefined)
  assert.equal(kpiLabel({ title: 'Total gross pay', statement: 'Total gross pay is ₹54.67 Cr.' }, '₹54.67 Cr'), undefined)
  const adds = '8.9% of the workforce left in 2025: 37 exits against an average headcount of 416.5.'
  assert.equal(kpiLabel({ title: 'Attrition in 2025', statement: adds }, '8.9%'), adds)
})

test('figures come first in a section, then charts, then the full-width ones', () => {
  const half = tile({ kind: 'trend', chart: chart({ type: 'line' }) })
  const kpi = tile({ kind: 'kpi', chart: chart({ type: 'kpi' }) })
  const full = tile({ kind: 'quality' })
  const packed = packTiles([half, full, kpi])
  assert.deepEqual(packed.map((t) => t.kind), ['kpi', 'trend', 'quality'])
  // Stable inside one width: the server's own order is the tie-breaker.
  const first = tile({ kind: 'breakdown', chart: chart({}), title: 'a' })
  const second = tile({ kind: 'share', chart: chart({ type: 'donut' }), title: 'b' })
  assert.deepEqual(packTiles([first, second]).map((t) => t.title), ['a', 'b'])
})
