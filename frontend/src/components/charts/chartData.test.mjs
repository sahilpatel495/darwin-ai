// Run: cd frontend && node --test "src/**/*.test.mjs"
//
// The dashboard fixture is the input for most of these: it is generated from the backend's own
// models, so every chart type the server can ask for is exercised against a shape the server
// really produces.
import test from 'node:test'
import assert from 'node:assert/strict'
import { buildChartData, fitTypes } from './chartData.ts'
import bar from '../../fixtures/answer_bar.json' with { type: 'json' }
import kpi from '../../fixtures/answer_kpi.json' with { type: 'json' }
import line from '../../fixtures/answer_line.json' with { type: 'json' }
import dashboard from '../../fixtures/dashboard.json' with { type: 'json' }

const spec = (over) => ({ type: 'bar', x: null, y: [], series: null, title: '', note: null, value_format: 'number', ...over })
const table = (columns, rows) => ({
  columns,
  rows,
  display: rows.map((r) => r.map((c) => (c === null ? '—' : String(c)))),
  row_count: rows.length,
  truncated: false,
})
/** A tile of the automatic dashboard, by id. */
const tile = (id) => {
  const found = dashboard.sections.flatMap((section) => section.tiles).find((t) => t.id === id)
  assert.ok(found, `fixture tile ${id}`)
  return found
}
const built = (id) => buildChartData(tile(id).chart, tile(id).table)

test('bar: labels come from display strings, values stay raw numbers', () => {
  const data = buildChartData(bar.chart, bar.table)
  assert.equal(data.kind, 'bar')
  assert.deepEqual(data.series, ['total_gross'])
  assert.deepEqual(data.points[0], { x: 'Engineering', values: [1200000] })
  assert.equal(data.points.length, 3)
})

test('bar: it turns horizontal only when a label is too long to sit under a column', () => {
  assert.equal(built('break-dept').horizontal, true, 'department names ("Customer Success")')
  const short = buildChartData(spec({ x: 'd', y: ['n'] }), table(['d', 'n'], [['HR', 3], ['Sales', 9]]))
  assert.equal(short.horizontal, false)
})

test('bar: only the first 12 groups are drawn, and the chart is told how many it left out', () => {
  const rows = Array.from({ length: 15 }, (_, i) => [`Dept ${i}`, 100 - i])
  const data = buildChartData(spec({ x: 'dept', y: ['n'] }), table(['dept', 'n'], rows))
  assert.equal(data.points.length, 12)
  assert.equal(data.points[11].x, 'Dept 11')
  assert.equal(data.omitted, 3)
  // A line is never trimmed: a trend with a missing tail is a different trend.
  const trend = buildChartData(spec({ type: 'line', x: 'dept', y: ['n'] }), table(['dept', 'n'], rows))
  assert.equal(trend.points.length, 15)
  assert.equal(trend.omitted, 0)
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

test('area: a trend is a trend — same points as a line, drawn with a fill', () => {
  const data = built('trend-pay')
  assert.equal(data.kind, 'area')
  assert.equal(data.points.length, 12)
  assert.equal(data.points[0].x, '2025-01', 'the month as the backend formatted it')
  assert.deepEqual(data.points[0].values, [43800000])
  assert.equal(data.horizontal, false, 'a trend never turns on its side')
})

test('histogram: every band is kept, in the order the bands were built', () => {
  const data = built('dist-ctc')
  assert.equal(data.kind, 'histogram')
  assert.deepEqual(data.points.map((p) => p.x), ['Under ₹5 L', '₹5–10 L', '₹10–15 L', '₹15–25 L', '₹25–40 L', 'Over ₹40 L'])
  assert.equal(data.omitted, 0)
  // Past 40 bands it is not a distribution anyone can read.
  const many = Array.from({ length: 41 }, (_, i) => [`band ${i}`, i])
  assert.equal(buildChartData(spec({ type: 'histogram', x: 'b', y: ['n'] }), table(['b', 'n'], many)).kind, 'table')
})

test('donut: biggest slice first, the total is the sum, and the tail becomes one "Other"', () => {
  const data = built('share-gender')
  assert.equal(data.kind, 'donut')
  assert.deepEqual(data.slices, [{ name: 'Male', value: 282 }, { name: 'Female', value: 205 }, { name: 'Not stated', value: 13 }])
  assert.equal(data.total, 500)
  assert.equal(data.otherCount, 0)

  const eight = Array.from({ length: 8 }, (_, i) => [`Team ${i}`, 10 - i])
  const folded = buildChartData(spec({ type: 'donut', x: 't', y: ['n'] }), table(['t', 'n'], eight))
  assert.equal(folded.slices.length, 7, 'six slices and an Other')
  assert.deepEqual(folded.slices[6], { name: 'Other', value: 7 }, '4 + 3, the two smallest')
  assert.equal(folded.otherCount, 2)
  assert.equal(folded.total, 52)
})

test('donut: a share of a negative, or of one thing, is not a share', () => {
  assert.equal(buildChartData(spec({ type: 'donut', x: 'd', y: ['n'] }), table(['d', 'n'], [['HR', 5], ['Sales', -2]])).kind, 'table')
  assert.equal(buildChartData(spec({ type: 'donut', x: 'd', y: ['n'] }), table(['d', 'n'], [['HR', 5]])).kind, 'table')
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

test('stacked bar: one bar per location, one segment per department', () => {
  const data = built('stack-loc')
  assert.equal(data.kind, 'stacked_bar')
  assert.deepEqual(data.series, ['Engineering', 'Sales', 'Support'])
  assert.deepEqual(data.points[0], { x: 'Bengaluru', values: [62, 28, 22] })
  assert.equal(data.points.length, 5)
  // A stack of a negative and a positive adds up to neither, so it stays a table.
  const mixed = table(['loc', 'dept', 'n'], [['A', 'x', 5], ['A', 'y', -1]])
  assert.equal(buildChartData(spec({ type: 'stacked_bar', x: 'loc', series: 'dept', y: ['n'] }), mixed).kind, 'table')
})

test('grouped bar: more series than there are colours falls back to the table with a reason', () => {
  const rows = ['a', 'b', 'c', 'd', 'e', 'f'].map((s) => ['Engineering', s, 1])
  const data = buildChartData(spec({ type: 'grouped_bar', x: 'd', series: 's', y: ['n'] }), table(['d', 's', 'n'], rows))
  assert.equal(data.kind, 'table')
  assert.match(data.reason, /table/)
})

test('heatmap: a grid of series against x, with the biggest cell setting the scale', () => {
  const data = built('heat-rating')
  assert.equal(data.kind, 'heatmap')
  assert.deepEqual(data.cols, ['L1', 'L2', 'L3', 'L4', 'L5'])
  assert.deepEqual(data.rows, ['1', '2', '3', '4', '5'], 'the rating, as the backend displayed it')
  assert.equal(data.cells.length, 5)
  assert.equal(data.cells[0][0], 6, 'L1, rating 1')
  assert.equal(data.max, Math.max(...data.cells.flat()))
  // A combination the query returned no row for is a gap, not a zero.
  const sparse = table(['g', 'r', 'n'], [['L1', '1', 3], ['L2', '2', 4]])
  const gaps = buildChartData(spec({ type: 'heatmap', x: 'g', series: 'r', y: ['n'] }), sparse)
  assert.deepEqual(gaps.cells, [[3, null], [null, 4]])
})

test('heatmap: past 12 rows or columns the cells are slivers, so it shows the table', () => {
  const rows = Array.from({ length: 26 }, (_, i) => [`Grade ${i}`, i % 2 ? 'A' : 'B', i])
  const data = buildChartData(spec({ type: 'heatmap', x: 'g', series: 'r', y: ['n'] }), table(['g', 'r', 'n'], rows))
  assert.equal(data.kind, 'table')
  assert.match(data.reason, /too many groups/)
  // All zeroes has no scale to colour by.
  const flat = table(['g', 'r', 'n'], [['L1', 'A', 0], ['L2', 'A', 0]])
  assert.equal(buildChartData(spec({ type: 'heatmap', x: 'g', series: 'r', y: ['n'] }), flat).kind, 'table')
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
  assert.equal(buildChartData(spec({ type: 'donut', x: 'department', y: ['missing'] }), t).kind, 'table')
  assert.equal(buildChartData(spec({ type: 'heatmap', x: 'department', y: ['n'] }), t).kind, 'table', 'no series column named')
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

test('the shapes offered are the ones that fit the result, in a fixed order', () => {
  assert.deepEqual(fitTypes(tile('break-dept').chart, tile('break-dept').table), ['bar', 'donut', 'table'])
  assert.deepEqual(fitTypes(tile('trend-pay').chart, tile('trend-pay').table), ['line', 'area', 'bar', 'table'])
  assert.deepEqual(fitTypes(tile('stack-loc').chart, tile('stack-loc').table), ['grouped_bar', 'stacked_bar', 'heatmap', 'table'])
  assert.deepEqual(fitTypes(tile('heat-rating').chart, tile('heat-rating').table), ['grouped_bar', 'stacked_bar', 'heatmap', 'table'])
  assert.deepEqual(fitTypes(tile('dist-ctc').chart, tile('dist-ctc').table), ['histogram', 'bar', 'table'])
  // The order never depends on what the server picked, so the control does not rearrange itself.
  const asDonut = { ...tile('break-dept').chart, type: 'donut' }
  assert.deepEqual(fitTypes(asDonut, tile('break-dept').table), ['bar', 'donut', 'table'])
})

test('a shape that would lie about this result is not offered', () => {
  // A share of a negative is not a share, so the donut is simply not among the options.
  const swings = table(['dept', 'net'], [['HR', 5], ['Sales', -2]])
  assert.deepEqual(fitTypes(spec({ x: 'dept', y: ['net'] }), swings), ['bar', 'table'])
  // A single value and a plain table offer nothing to switch between.
  assert.deepEqual(fitTypes(kpi.chart, kpi.table), [])
  assert.deepEqual(fitTypes(spec({ type: 'table' }), swings), [])
})

test('a donut is offered only for a measure that adds up', () => {
  const table = {
    columns: ['department', 'avg_salary'],
    rows: [['Support', 134000], ['Engineering', 110000], ['Sales', 99612]],
    display: [['Support', '₹1.34 L'], ['Engineering', '₹1.10 L'], ['Sales', '₹99,612']],
    row_count: 3,
    truncated: false,
  }
  const spec = { type: 'bar', x: 'department', y: ['avg_salary'], series: null, title: '', note: null, value_format: 'currency_inr' }
  assert.deepEqual(fitTypes(spec, table), ['bar', 'table'], 'the average of a department is not a slice of anything')
  const total = { ...spec, y: ['total_gross'] }
  assert.deepEqual(fitTypes(total, { ...table, columns: ['department', 'total_gross'] }), ['bar', 'donut', 'table'])
  // The server saw the query: when it chose the donut itself, the donut stays on offer.
  assert.ok(fitTypes({ ...spec, type: 'donut' }, table).includes('donut'))
})
