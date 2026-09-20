// Draws the real components to HTML and checks what a person (or an attacker) would get.
// Run: cd frontend && node --test "src/**/*.test.mjs"
//
// No test framework is installed, so this uses what is: Vite's SSR loader reads the .tsx files
// and react-dom/server draws them. Effects and clicks do not run here; those belong to the
// Playwright smoke test. What this does catch: a crash while drawing, text that is not inert,
// and a missing label, caveat or message.
import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { tmpdir } from 'node:os'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import bar from '../../fixtures/answer_bar.json' with { type: 'json' }
import kpi from '../../fixtures/answer_kpi.json' with { type: 'json' }
import clarify from '../../fixtures/answer_clarify.json' with { type: 'json' }
import refusal from '../../fixtures/answer_refusal.json' with { type: 'json' }
import catalog from '../../fixtures/catalog.json' with { type: 'json' }
import dashboard from '../../fixtures/dashboard.json' with { type: 'json' }
import report from '../../fixtures/eval_report.json' with { type: 'json' }

const HOSTILE = '<script>alert(1)</script> ![x](http://evil.test/a.png) [click](javascript:alert(1)) <img src=x onerror=alert(1)>'

let vite
let AnswerStatement, AnswerContext, DataTable, ResultView, Working, Thread, trustReport, barEndLabel, buildChartData

before(async () => {
  vite = await createServer({
    root: new URL('../../..', import.meta.url).pathname,
    configFile: false, // no Tailwind or proxy needed to draw markup
    cacheDir: `${tmpdir()}/verity-render-test`, // never touch the dev server's cache
    appType: 'custom',
    logLevel: 'error',
    server: { middlewareMode: true, ws: false, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true },
  })
  const load = async (path) => vite.ssrLoadModule(path)
  AnswerStatement = (await load('/src/components/answer/AnswerStatement.tsx')).default
  AnswerContext = (await load('/src/components/answer/context.ts')).AnswerContext
  DataTable = (await load('/src/components/charts/DataTable.tsx')).default
  ResultView = (await load('/src/components/charts/ResultView.tsx')).default
  buildChartData = (await load('/src/components/charts/chartData.ts')).buildChartData
  barEndLabel = (await load('/src/components/charts/ResultChart.tsx')).barEndLabel
  Working = (await load('/src/components/thread/Working.tsx')).default
  Thread = (await load('/src/components/thread/Thread.tsx')).default
  trustReport = await load('/src/pages/TrustReport.tsx')
})
after(() => vite.close())

const noop = () => {}
/** One answer as the thread draws it: the context is what the Thread supplies around it. */
const statement = (answer, props = {}, context = {}) =>
  renderToStaticMarkup(
    h(
      AnswerContext.Provider,
      { value: { tables: catalog.tables, glossary: [], newAnswerId: null, tourAnswerId: null, canAsk: true, ...context } },
      h(AnswerStatement, { answer, mode: 'thread', onAsk: noop, onToggleSaved: noop, ...props }),
    ),
  )
const thread = (props = {}) =>
  renderToStaticMarkup(
    h(Thread, {
      sessionId: 's',
      catalog,
      turns: [],
      onTurnsChange: noop,
      savedAnswerIds: [],
      onToggleSaved: noop,
      onSessionExpired: noop,
      emptyState: h('p', null, 'Here is what I found in your files'),
      ...props,
    }),
  )
const result = (chart, table, props = {}) =>
  renderToStaticMarkup(h(ResultView, { chart, table, data: chart ? buildChartData(chart, table) : null, question: 'q', allowSwitch: true, ...props }))
const working = (props) => renderToStaticMarkup(h(Working, { steps: [], running: false, ...props }))
const step = (stage, status, detail = '') => ({ stage, status, detail })
const tile = (id) => dashboard.sections.flatMap((section) => section.tiles).find((t) => t.id === id)
/** Visible words only, so assertions read like the page. Spans are inline: no space is added. */
const words = (html) => html.replace(/<\/?span[^>]*>/g, '').replace(/<[^>]+>/g, ' ').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/\s+/g, ' ').trim()
/** The way React writes text into HTML. If a string shows up like this, it was never markup. */
const escaped = (text) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;')
const tableOf = (rows, display = rows.map((r) => r.map((c) => (c === null ? '—' : String(c))))) => ({ columns: ['dept', 'amount'], rows, display, row_count: rows.length, truncated: false })

test('text from the model and from the file is inert: no tags, links or images are ever created', () => {
  const answer = {
    ...bar,
    text: HOSTILE,
    followups: [HOSTILE],
    insights: [HOSTILE],
    chart: { ...bar.chart, title: HOSTILE, note: HOSTILE },
    table: { ...bar.table, columns: [HOSTILE, 'total_gross'], display: bar.table.display.map((row) => [HOSTILE, row[1]]) },
    work: {
      ...bar.work,
      reading: HOSTILE,
      plan: [HOSTILE],
      caveats: [HOSTILE],
      assumptions: [HOSTILE],
      attempts: [{ sql: HOSTILE, model: HOSTILE, reason: 'sql_error', error: HOSTILE }],
      payloads: [{ purpose: 'generate', provider: HOSTILE, model: HOSTILE, cached: false, latency_ms: 12, messages: [{ role: HOSTILE, content: HOSTILE }] }],
    },
  }
  for (const html of [
    statement(answer),
    renderToStaticMarkup(h(DataTable, { table: answer.table, caption: HOSTILE })),
    working({ steps: [step('execute', 'failed', HOSTILE)] }),
  ]) {
    assert.doesNotMatch(html, /<script|<img|<a\s|href=|<iframe/i)
    assert.ok(html.includes(escaped(HOSTILE)), 'the text is shown exactly as written')
  }
})

test('an answer with no chart and no table is just the sentence, its proof and the working', () => {
  const html = statement({ ...bar, chart: null, table: null })
  assert.ok(words(html).startsWith(bar.text))
  assert.doesNotMatch(html, /<table|<figure/)
  assert.match(html, /How I got this/)
})

test('a very long answer wraps instead of pushing the page sideways', () => {
  assert.match(statement({ ...bar, text: 'x'.repeat(20000) }), /<h3 class="[^"]*break-words[^"]*">x{20000}<\/h3>/)
})

test('a confidence level or step status this build does not know is skipped, not a crash', () => {
  assert.doesNotMatch(statement({ ...bar, confidence: { level: 'very_high', score: 1, reasons: [] } }), /confidence/i)
  const steps = words(working({ steps: [step('rerank', 'skipped', 'new in a later server')] }))
  assert.match(steps, /rerank/)
  assert.match(steps, /new in a later server/)
})

test('kind error: the server sentence and nothing added to it, then Try again', () => {
  const error = { ...bar, kind: 'error', text: 'The database could not run this query.', chart: null, table: null }
  assert.equal(words(statement(error)), 'The database could not run this query. Try again')
  assert.match(words(statement({ ...error, text: '' })), /^This question could not be answered\./)
  // While another question runs the button keeps its place, disabled, so nothing moves.
  assert.match(statement(error, {}, { canAsk: false }), /<button type="button" disabled=""/)
  assert.doesNotMatch(statement(error, { mode: 'board' }), /<button/)
})

test('a rate-limited error counts its own wait down and stays disabled until zero', () => {
  const html = statement({ ...bar, kind: 'error', text: 'Too many questions in a minute.', retry_after_s: 12, chart: null, table: null })
  assert.match(words(html), /Too many questions in a minute\. Try again in 12 s/)
  assert.match(html, /<button type="button" disabled=""/)
})

test('clarify offers each meaning as a chip, even when two options share a value', () => {
  const html = statement({ ...clarify, clarification: { ...clarify.clarification, options: [...clarify.clarification.options, clarify.clarification.options[0]] } })
  assert.equal(html.match(/CTC, annual/g).length, 2)
  assert.match(words(html), /Which salary figure do you mean\?/)
})

test('the analyst reads file names, not SQL table names, and is not asked the same sentence twice', () => {
  const tables = [{ name: 'pay_2025_register', source_file: 'Pay_2025.xlsx', sheet: 'Register', columns: [{ name: 'gross', label: 'Gross' }] }]
  const asked = { ...clarify, text: 'Which one?', clarification: { term: 'salary', question: 'which one?', options: [{ label: 'Gross pay (pay_2025_register.gross)', value: 'pay_2025_register.gross' }, clarify.clarification.options[0]] } }
  const html = words(statement(asked, {}, { tables }))
  assert.equal(html.match(/which one\?/gi).length, 1)
  assert.match(html, /Gross pay — Gross in Pay_2025\.xlsx/)
  assert.ok(!html.includes('pay_2025_register'))
  const caveat = words(statement({ ...bar, work: { ...bar.work, caveats: ['6 exact duplicate rows were removed from pay_2025_register before answering.'] } }, {}, { tables }))
  assert.match(caveat, /Keep in mind 6 exact duplicate rows were removed from Pay_2025\.xlsx before answering\./)
})

test('the verified lines are generated from the answer, and a disagreement is a banner, not a check', () => {
  const agreed = words(statement(bar))
  assert.match(agreed, /Computed by a database from your files/)
  assert.match(agreed, /A second AI model wrote its own query and got the same result/)
  assert.match(agreed, /No rows or personal data were sent to the AI\. See exactly what was sent/)
  const disagreed = words(statement(kpi))
  assert.doesNotMatch(disagreed, /got the same result/)
  assert.match(disagreed, /A second AI model wrote its own query and got a different result\./)
  assert.match(disagreed, /Check this figure before you pass it on\./)
})

test('only a newly arrived answer pops its checks, and never on the board', () => {
  assert.doesNotMatch(statement(bar), /check-pop/)
  assert.match(statement(bar, {}, { newAnswerId: bar.id }), /check-pop/)
  assert.doesNotMatch(statement(bar, { mode: 'board' }, { newAnswerId: bar.id }), /check-pop/)
})

test('a single value is the hero figure, with its supporting counts beside it', () => {
  const html = statement(kpi)
  assert.match(words(html), /28\.6% Attrition rate, 2025 Exits 2 Avg headcount 7/)
  assert.match(html, /type-hero/, 'the hero figure')
  assert.doesNotMatch(words(html), /Download CSV/, 'one number needs no spreadsheet')
})

test('what the server computed from the result is shown as chips, word for word', () => {
  const html = words(statement({ ...bar, insights: ['Median ₹10.4 L', 'Top 10% earn above ₹28.0 L'] }))
  assert.match(html, /Median ₹10\.4 L/)
  assert.match(html, /Top 10% earn above ₹28\.0 L/)
})

test('a cached answer says so quietly, in the analyst’s words', () => {
  assert.match(words(statement({ ...bar, work: { ...bar.work, cached: true } })), /Same question, same data: answered from memory\./)
})

test('the board is the statement without the controls', () => {
  const html = statement(bar, { mode: 'board', saved: true })
  assert.doesNotMatch(html, /<button/)
  assert.match(words(html), /Computed by a database from your files/)
  assert.match(words(html), /Keep in mind/)
})

test('the answer can be copied, saved and taken apart; the board can do none of those', () => {
  const html = words(statement(bar))
  assert.match(html, /Save to board/)
  assert.match(html, /Copy answer/)
  assert.match(html, /How I got this/)
  assert.doesNotMatch(words(statement(bar, { mode: 'board' })), /Copy answer/)
})

test('the result offers the shapes that fit it, and always the table and the file', () => {
  const html = result(bar.chart, bar.table)
  assert.match(words(html), /Bar Donut Table/, 'a breakdown by department is also a share')
  assert.match(words(html), /Download CSV/)
  assert.match(html, /aria-label="Open the chart larger"/)
  assert.match(html, /role="radiogroup" aria-label="Show the result as"/)
  // A trend is a line, an area or a bar — never a donut.
  assert.match(words(result(tile('trend-pay').chart, tile('trend-pay').table)), /Line Area Bar Table/)
  assert.match(words(result(tile('stack-loc').chart, tile('stack-loc').table)), /Grouped Stacked Heatmap Table/)
})

test('every shape the backend can ask for draws, and says what it is', () => {
  // Recharts needs a width to draw into, which SSR has none of, so what is checked here is the
  // part this app owns: it does not crash, and the words around the plot are right.
  const drawn = (id, type) => {
    const t = tile(id)
    return words(result({ ...t.chart, type }, t.table, { data: null }))
  }
  for (const [id, type, name] of [
    ['break-dept', 'bar', 'Bar chart'],
    ['trend-pay', 'line', 'Line chart'],
    ['trend-pay', 'area', 'Area chart'],
    ['dist-ctc', 'histogram', 'Histogram'],
    ['stack-loc', 'grouped_bar', 'Grouped bar chart'],
    ['stack-loc', 'stacked_bar', 'Stacked bar chart'],
  ]) {
    const html = renderToStaticMarkup(h(ResultView, { chart: { ...tile(id).chart, type }, table: tile(id).table, allowSwitch: true }))
    assert.match(html, new RegExp(`aria-label="[^"]*${name}`), `${type} names itself for a screen reader`)
  }
  // The two this app draws itself, rather than handing to Recharts.
  const donut = drawn('share-gender', 'donut')
  assert.match(donut, /500 Total/, 'the total sits in the middle')
  assert.match(donut, /Male56%/, 'each slice with its share')
  const heat = drawn('heat-rating', 'heatmap')
  assert.match(heat, /L1L2L3L4L5/, 'the columns, one cell each')
  assert.match(heat, /042Employees/, 'the scale legend runs from nothing to the biggest cell, named by what it counts')
  // Scatter has no dashboard tile: two measures and a label column.
  const scatter = { columns: ['department', 'avg_ctc', 'avg_rating'], rows: [['HR', 900000, 3.5]], display: [['HR', '₹9.00 L', '3.5']], row_count: 1, truncated: false }
  const spec = { type: 'scatter', x: 'avg_ctc', y: ['avg_rating'], series: null, title: 'Pay against rating', note: null, value_format: 'number' }
  assert.match(renderToStaticMarkup(h(ResultView, { chart: spec, table: scatter, allowSwitch: true })), /aria-label="[^"]*Scatter chart/)
})

test('a tile draws the chart alone: no switch, no download, no dialog', () => {
  const html = result(tile('share-gender').chart, tile('share-gender').table, { allowSwitch: false, data: null })
  assert.doesNotMatch(html, /<button/)
  assert.doesNotMatch(html, /radiogroup/)
  // Both props optional, and a tile with no result at all draws nothing rather than crashing.
  assert.equal(renderToStaticMarkup(h(ResultView, { chart: null, table: null })), '')
})

test('the table view offers the rows as a CSV; an empty result offers nothing to download', () => {
  assert.match(words(result(null, tableOf([['HR', 1], ['Sales', 2]]))), /Download CSV/)
  assert.ok(!result(null, tableOf([])).includes('Download CSV'))
  assert.ok(!result(bar.chart, bar.table, { allowSwitch: false }).includes('Download CSV'), 'the board prints one view')
})

test('refusal says what would make the question answerable', () => {
  assert.match(words(statement(refusal)), new RegExp(`What would make this answerable ${refusal.missing.slice(0, 40).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
})

test('How I got this opens with the route the answer took, then the working in full', () => {
  const html = words(statement(bar))
  // Six nodes, in order; the label and its note are two lines inside one pill, so they join here.
  for (const node of ['Your question', 'Query writtenopenai/gpt-oss-120b', 'Safety checkRejected once, then rewritten', 'Your data24 rows read', 'Second modelAgreed']) {
    assert.ok(html.includes(node), node)
  }
  assert.match(html, /Rewritten once/, 'the repaired query loops back')
  // The sections under it are all still there.
  for (const heading of ['Plan', 'Data used', 'SQL', 'Cross-check', 'Attempts (2)', 'What the model saw']) assert.ok(html.includes(heading), heading)
})

test('How I got this carries the privacy line and the model messages word for word', () => {
  const html = statement(bar)
  // The line must match what the payloads below it show: category values are sent, rows are not.
  assert.match(words(html), /short lists of category values \(such as department names\) were sent\. No rows, and nothing from a personal data column\./)
  for (const payload of bar.work.payloads) for (const message of payload.messages) assert.ok(html.includes(escaped(message.content)))
  assert.match(html, /Copy SQL/)
  assert.match(html, /data-section="payloads"/, 'the privacy line has somewhere to jump to')
})

test('the first answer in a thread is the one the tour points at', () => {
  assert.match(statement(bar, {}, { tourAnswerId: bar.id }), /data-tour="working"/)
  assert.doesNotMatch(statement(bar, {}, { tourAnswerId: 'another' }), /data-tour="working"/)
})

test('table: one row needs no footnote; 5,000 rows draw 200 and say so; an empty cell is a dash', () => {
  const one = renderToStaticMarkup(h(DataTable, { table: tableOf([['HR', null]]), caption: 'Pay' }))
  assert.equal(words(one), 'Pay Dept Amount HR —')
  const many = renderToStaticMarkup(h(DataTable, { table: tableOf(Array.from({ length: 5000 }, (_, i) => [`D${i}`, -25000000 * i])), caption: 'Pay' }))
  assert.equal(many.match(/<tr/g).length, 201)
  assert.match(words(many), /Showing the first 200 rows\. The full result is longer\./)
  assert.match(many, /<th[^>]*text-right[^>]*>Amount/, 'numbers are right-aligned')
  assert.match(many, /<th[^>]*sticky top-0/, 'the header stays while the rows scroll')
})

test('result view: an empty result is one sentence, with no furniture around it', () => {
  assert.equal(words(result(bar.chart, { ...bar.table, rows: [], display: [], row_count: 0 })), 'The query ran and returned no rows.')
})

test('bar labels: a negative bar is labelled right of the zero line, never over the department name', () => {
  const label = barEndLabel('currency_inr')
  // Recharts describes a negative bar as starting at zero with a negative width.
  assert.match(renderToStaticMarkup(label({ x: 100, y: 10, width: -40, height: 20, value: -300000000 })), /<text x="106" y="20"[^>]*>-₹30\.00 Cr<\/text>/)
  assert.match(renderToStaticMarkup(label({ x: 100, y: 10, width: 40, height: 20, value: 99999.5 })), /<text x="146"[^>]*>₹99,999\.50<\/text>/)
  assert.equal(label({ x: 100, y: 10, width: 0, height: 20, value: null }), null, 'an empty cell has no label')
})

test('working: the card names what is happening, who is writing and how long it has taken', () => {
  const html = working({
    steps: [step('understand', 'ok', 'No ambiguous terms'), step('generate', 'ok', 'openai/gpt-oss-120b wrote a 3-step plan'), step('guard', 'started')],
    running: true,
    startedAt: 0,
    onStop: noop,
  })
  const text = words(html)
  assert.match(text, /Working on it/)
  assert.match(text, /openai\/gpt-oss-120b/, 'the model, as a chip')
  assert.match(text, /Stop/)
  assert.match(text, /Understanding the question No ambiguous terms/)
  assert.match(text, /Double-checking with a second AI model/, 'the steps still to come are listed')
  assert.match(html, /shimmer/, 'the skeleton of the answer that is coming')
})

test('working: the models being busy reads as a wait with a countdown, not as an error', () => {
  const html = words(working({ steps: [step('generate', 'warn', 'All the free AI models are busy. Retrying in 12 seconds.')], running: true, startedAt: 0 }))
  assert.match(html, /All the free AI models are busy\. Trying again in 12 s\./)
})

test('working: once answered it folds to one line, and a failed step is named as failed', () => {
  const html = working({ steps: [step('guard', 'ok', ''), step('execute', 'failed', 'The query took too long.')], ms: 3247 })
  assert.match(words(html), /Answered in 3\.2 s, 2 checks, 1 failed/)
  assert.match(words(html), /Running it on your data The query took too long\./)
  assert.match(html, /aria-label="Failed"/, 'the state is in words for a screen reader too')
  assert.match(html, /check-pop/, 'a finished step pops the same check the verified lines use')
  assert.equal(working({ steps: [], running: false }), '', 'a turn with no timeline shows nothing at all')
})

test('thread: an empty thread is the briefing, a labelled composer and how to word a question', () => {
  const html = thread()
  assert.match(words(html), /Here is what I found in your files/)
  assert.match(html, /<label for="verity-question"/)
  assert.match(html, /<button type="submit" disabled=""/, 'nothing to ask yet')
  assert.match(html, /data-tour="composer"/)
  assert.match(words(html), /Name the measure: “gross pay”, not “pay”\./)
  // Screen-reader-only text is absolutely positioned. If the scroller is not `relative`, that text is laid
  // out against the page, the page grows as tall as the conversation, and the header scrolls away.
  assert.match(html, /class="relative [^"]*overflow-y-auto/)
})

test('thread: with no files loaded the history still reads and the composer is closed', () => {
  const html = thread({ sessionId: null, catalog: null, turns: [{ id: bar.id, question: bar.question, answer: bar, askedAt: '2025-01-01T00:00:00Z' }], notice: h('p', null, 'Your files are no longer loaded.') })
  assert.match(words(html), /Your files are no longer loaded\./)
  assert.ok(words(html).includes(bar.text), 'the answer is still readable')
  assert.match(html, /<textarea[^>]*disabled=""/)
  assert.doesNotMatch(words(html), /Name the period/, 'no advice about a question that cannot be asked')
})

test('thread: a saved answer says Saved, and a clarifying question cannot be saved at all', () => {
  const turn = (answer) => [{ id: answer.id, question: answer.question, answer, askedAt: '2025-01-01T00:00:00Z' }]
  assert.match(words(thread({ turns: turn(bar), savedAnswerIds: [bar.id] })), /Saved/)
  assert.match(words(thread({ turns: turn(bar) })), /Save to board/)
  assert.doesNotMatch(words(thread({ turns: turn({ ...clarify, id: 'c1' }) })), /Save to board/)
})

test('trust report: the fixture reads as sentences and shows why a question failed', () => {
  const page = words(renderToStaticMarkup(h(trustReport.Report, { report })))
  assert.match(page, /40 test questions, run 3 times with openai\/gpt-oss-120b\./)
  assert.match(page, /Correct answers 92\.5%/)
  assert.match(page, /higher confidence went with higher accuracy/)
  const failed = report.cases.find((c) => !c.passed)
  if (failed) assert.ok(page.includes(failed.note))
})

test('trust report: an empty run has no empty headings; an unreadable file is refused before drawing', () => {
  const empty = { ...report, total: 0, runs: 0, by_category: {}, calibration: {}, models: [], cases: [], crosscheck_agreement: null }
  const page = words(renderToStaticMarkup(h(trustReport.Report, { report: empty })))
  assert.doesNotMatch(page, /Accuracy by type of question|Models compared/)
  assert.match(page, /not enough rated answers/)
  assert.match(page, /Second model agreed Not measured/)
  assert.match(page, /This report lists no individual questions\./)
  // A tuning-only run holds no unseen questions: "0%" would read as a failure.
  const devOnly = { ...report, accuracy_holdout: 0, cases: report.cases.filter((c) => c.split !== 'holdout') }
  assert.match(words(renderToStaticMarkup(h(trustReport.Report, { report: devOnly }))), /Correct on unseen questions Not measured/)
  assert.equal(trustReport.isReadable(report), true)
  for (const broken of [{}, null, 'oops', { ...report, cases: null }, { ...report, trust_score: undefined }]) assert.equal(trustReport.isReadable(broken), false)
})
