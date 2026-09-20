// Run: cd frontend && node --test "src/**/*.test.mjs"
import test from 'node:test'
import assert from 'node:assert/strict'
import { buildChartData } from './chartData.ts'
import bar from '../../fixtures/answer_bar.json' with { type: 'json' }
import kpi from '../../fixtures/answer_kpi.json' with { type: 'json' }
import line from '../../fixtures/answer_line.json' with { type: 'json' }

const spec = (over) => ({ type: 'bar', x: null, y: [], series: null, title: '', note: null, value_format: 'number', ...over })
const table = (columns, rows) => ({
  columns,
  rows,
  display: rows.map((r) => r.map((c) => (c === null ? '—' : String(c)))),
  row_count: rows.length,
  truncated: false,
})

test('bar: labels come from display strings, values stay raw numbers', () => {
  const data = buildChartData(bar.chart, bar.table)
  assert.equal(data.kind, 'bar')
  assert.deepEqual(data.series, ['total_gross'])
  assert.deepEqual(data.points[0], { x: 'Engineering', values: [1200000] })
  assert.equal(data.points.length, 3)
})

test('bar: only the first 12 groups are drawn, and the chart is told how many it left out', () => {
  const rows = Array.from({ length: 15 }, (_, i) => [`Dept ${i}`, 100 - i])
  const data = buildChartData(spec({ x: 'dept', y: ['n'] }), table(['dept', 'n'], rows))
  assert.equal(data.points.length, 12)
  assert.equal(data.points[11].x, 'Dept 11')
  assert.equal(data.omitted, 3)
  // A line is never trimmed: a trend with a missing tail is a different trend.
  const line = buildChartData(spec({ type: 'line', x: 'dept', y: ['n'] }), table(['dept', 'n'], rows))
  assert.equal(line.points.length, 15)
  assert.equal(line.omitted, 0)
})

test('kpi: the big value is the display string of the measured column, the rest is supporting', () => {
  const data = buildChartData(kpi.chart, kpi.table)
  assert.equal(data.kind, 'kpi')
  assert.equal(data.value, '28.6%')
  assert.deepEqual(data.supporting, [
    { label: 'exits', value: '2' },
    { label: 'avg_headcount', value: '7' },
  ])
})

test('line: one point per row, in the order the database returned them', () => {
  const data = buildChartData(line.chart, line.table)
  assert.equal(data.kind, 'line')
  assert.deepEqual(data.points.map((p) => p.x), ['01/2025', '02/2025', '03/2025', '04/2025', '05/2025', '06/2025'])
  assert.deepEqual(data.points[5].values, [172])
})

test('grouped bar: rows are pivoted by the series column, gaps stay empty', () => {
  const t = table(
    ['department', 'level', 'headcount'],
    [
      ['Engineering', 'Sr. Manager', 4],
      ['Engineering', 'Analyst', 9],
      ['HR', 'Analyst', 3],
    ],
  )
  const data = buildChartData(spec({ type: 'grouped_bar', x: 'department', series: 'level', y: ['headcount'] }), t)
  assert.equal(data.kind, 'grouped_bar')
  assert.deepEqual(data.series, ['Sr. Manager', 'Analyst'])
  assert.deepEqual(data.points, [
    { x: 'Engineering', values: [4, 9] },
    { x: 'HR', values: [null, 3] },
  ])
})

test('grouped bar: more series than there are colours falls back to the table with a reason', () => {
  const rows = ['a', 'b', 'c', 'd', 'e', 'f'].map((s) => ['Engineering', s, 1])
  const data = buildChartData(spec({ type: 'grouped_bar', x: 'd', series: 's', y: ['n'] }), table(['d', 's', 'n'], rows))
  assert.equal(data.kind, 'table')
  assert.match(data.reason, /table/)
})

test('scatter: x and y are the two measures the backend names, the first other column labels the point', () => {
  const t = table(['department', 'avg_ctc', 'avg_rating'], [['HR', 900000, 3.5], ['Sales', null, 4]])
  const data = buildChartData(spec({ type: 'scatter', x: 'avg_ctc', y: ['avg_rating'] }), t)
  assert.equal(data.kind, 'scatter')
  assert.deepEqual(data.points, [{ x: 900000, y: 3.5, label: 'HR', xDisplay: '900000', yDisplay: '3.5' }])
  assert.equal(data.xLabel, 'avg_ctc')
  assert.equal(buildChartData(spec({ type: 'scatter', y: ['avg_ctc', 'avg_rating'] }), t).kind, 'table', 'no x column named: nothing is guessed')
})

test('fails closed: a spec that does not fit the table shows the table instead of a broken chart', () => {
  const t = table(['department', 'n'], [['HR', 3]])
  assert.equal(buildChartData(spec({ x: 'department', y: ['missing_column'] }), t).kind, 'table')
  assert.equal(buildChartData(spec({ x: 'department', y: [] }), t).kind, 'table')
  assert.equal(buildChartData(spec({ x: 'department', y: ['department'] }), t).kind, 'table', 'no numeric values')
  assert.equal(buildChartData(spec({ type: 'kpi', y: ['n'] }), table(['n'], [])).kind, 'table', 'empty result')
  assert.equal(buildChartData(spec({ type: 'kpi' }), table(['a', 'b'], [[1, 2]])).kind, 'table', 'kpi must not guess which number to headline')
  assert.equal(buildChartData(spec({ type: 'kpi' }), table(['n'], [[7]])).value, '7', 'a single cell needs no column name')
})

test('kpi: a result with several rows is never headlined, whatever the spec says', () => {
  const data = buildChartData(spec({ type: 'kpi', y: ['n'] }), table(['dept', 'n'], [['HR', null], ['Sales', 9]]))
  assert.equal(data.kind, 'table', 'row 0 is not "the" answer when there are two rows')
})

test('grouped bar: more than 12 groups shows the table instead of silently dropping some', () => {
  const rows = Array.from({ length: 26 }, (_, i) => [`Dept ${i >> 1}`, i % 2 ? 'Male' : 'Female', i])
  const data = buildChartData(spec({ type: 'grouped_bar', x: 'dept', series: 'gender', y: ['n'] }), table(['dept', 'gender', 'n'], rows))
  assert.equal(data.kind, 'table')
  assert.match(data.reason, /too many groups/)
})

test('bar: 40 groups with negative, crore-scale and empty values keep their raw numbers', () => {
  const rows = Array.from({ length: 40 }, (_, i) => [`Dept ${i}`, i === 1 ? null : -25000000 * (i + 1)])
  const data = buildChartData(spec({ x: 'dept', y: ['net_change'], value_format: 'currency_inr' }), table(['dept', 'net_change'], rows))
  assert.equal(data.points.length, 12)
  assert.deepEqual(data.points.slice(0, 2), [{ x: 'Dept 0', values: [-25000000] }, { x: 'Dept 1', values: [null] }])
})

test('line: every row of a long trend is kept, and text in a measure column becomes a gap', () => {
  const rows = Array.from({ length: 5000 }, (_, i) => [`day ${i}`, i === 3 ? 'n/a' : i])
  const data = buildChartData(spec({ type: 'line', x: 'day', y: ['n'] }), table(['day', 'n'], rows))
  assert.equal(data.points.length, 5000)
  assert.deepEqual(data.points[3].values, [null])
})

test('a table spec is not an error, so it carries no reason', () => {
  assert.deepEqual(buildChartData(spec({ type: 'table' }), table(['a'], [['x']])), { kind: 'table', reason: null })
})
