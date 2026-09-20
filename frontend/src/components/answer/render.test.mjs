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
import report from '../../fixtures/eval_report.json' with { type: 'json' }

const HOSTILE = '<script>alert(1)</script> ![x](http://evil.test/a.png) [click](javascript:alert(1)) <img src=x onerror=alert(1)>'

let vite
let AnswerCard, DataTable, ResultView, StepList, Thread, trustReport, barEndLabel

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
  AnswerCard = (await load('/src/components/answer/AnswerCard.tsx')).default
  DataTable = (await load('/src/components/charts/DataTable.tsx')).default
  ResultView = (await load('/src/components/charts/ResultView.tsx')).default
  barEndLabel = (await load('/src/components/charts/ResultChart.tsx')).barEndLabel
  StepList = (await load('/src/components/thread/StepList.tsx')).default
  Thread = (await load('/src/components/thread/Thread.tsx')).default
  trustReport = await load('/src/pages/TrustReport.tsx')
})
after(() => vite.close())

const noop = () => {}
const card = (answer, props = {}) => renderToStaticMarkup(h(AnswerCard, { answer, glossary: [], tables: catalog.tables, busy: false, onAsk: noop, onClarify: noop, onRetry: noop, ...props }))
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
  for (const html of [card(answer), renderToStaticMarkup(h(DataTable, { table: answer.table, caption: HOSTILE })), renderToStaticMarkup(h(StepList, { running: false, steps: [{ stage: 'execute', status: 'failed', detail: HOSTILE }] }))]) {
    assert.doesNotMatch(html, /<script|<img|<a\s|href=|<iframe/i)
    assert.ok(html.includes(escaped(HOSTILE)), 'the text is shown exactly as written')
  }
})

test('an answer with no chart and no table is just the words, badges and working', () => {
  const html = card({ ...bar, chart: null, table: null })
  assert.ok(words(html).startsWith(bar.text))
  assert.doesNotMatch(html, /<table|<figure/)
  assert.match(html, /How I got this/)
})

test('a very long answer wraps instead of pushing the page sideways', () => {
  const html = card({ ...bar, text: 'x'.repeat(20000) })
  assert.match(html, /<p class="[^"]*break-words[^"]*">x{20000}<\/p>/)
})

test('a confidence level or step status this build does not know is skipped, not a crash', () => {
  assert.doesNotMatch(card({ ...bar, confidence: { level: 'very_high', score: 1, reasons: [] } }), /confidence/)
  const steps = words(renderToStaticMarkup(h(StepList, { running: false, steps: [{ stage: 'rerank', status: 'skipped', detail: 'new in a later server' }] })))
  assert.match(steps, /rerank: new in a later server/)
})

test('kind error: what happened, what to do next, and Retry; no Retry while another question runs', () => {
  const error = { ...bar, kind: 'error', text: 'The database could not run this query.', chart: null, table: null }
  assert.equal(words(card(error)), 'The database could not run this query. Ask it again, or try wording it differently. Try again')
  assert.doesNotMatch(card(error, { busy: true }), /<button/)
  assert.match(words(card({ ...error, text: '' })), /^This question could not be answered\./)
})

test('clarify offers each meaning as a chip, even when two options share a value', () => {
  const html = card({ ...clarify, clarification: { ...clarify.clarification, options: [...clarify.clarification.options, clarify.clarification.options[0]] } })
  assert.equal(html.match(/CTC, annual/g).length, 2)
  assert.match(words(html), /Which salary figure do you mean\?/)
})

test('the analyst reads file names, not SQL table names, and is not asked the same sentence twice', () => {
  const tables = [{ name: 'pay_2025_register', source_file: 'Pay_2025.xlsx', sheet: 'Register', columns: [{ name: 'gross', label: 'Gross' }] }]
  const asked = { ...clarify, text: 'Which one?', clarification: { term: 'salary', question: 'which one?', options: [{ label: 'Gross pay (pay_2025_register.gross)', value: 'pay_2025_register.gross' }, clarify.clarification.options[0]] } }
  const html = words(card(asked, { tables }))
  assert.equal(html.match(/which one\?/gi).length, 1)
  assert.match(html, /Gross pay · Gross in Pay_2025\.xlsx/)
  assert.ok(!html.includes('pay_2025_register'))
  const caveat = words(card({ ...bar, work: { ...bar.work, caveats: ['6 exact duplicate rows were removed from pay_2025_register before answering.'] } }, { tables }))
  assert.match(caveat, /removed from Pay_2025\.xlsx before answering\./)
})

test('the table view offers the rows as a CSV; the chart view and an empty result do not', () => {
  const tableOnly = words(renderToStaticMarkup(h(ResultView, { chart: null, table: tableOf([['HR', 1], ['Sales', 2]]), question: 'Pay by dept?' })))
  assert.match(tableOnly, /Download CSV \(2 rows\)/)
  assert.ok(!words(renderToStaticMarkup(h(ResultView, { chart: bar.chart, table: bar.table, question: 'q' }))).includes('Download CSV'), 'chart view first')
  assert.ok(!words(renderToStaticMarkup(h(ResultView, { chart: null, table: tableOf([]), question: 'q' }))).includes('Download CSV'))
})

test('refusal says what would make the question answerable', () => {
  assert.match(words(card(refusal)), new RegExp(`What would make this answerable ${refusal.missing.slice(0, 40).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
})

test('How I got this carries the privacy line and the model messages word for word', () => {
  const html = card(bar)
  // The line must match what the payloads below it show: category values are sent, rows are not.
  assert.match(words(html), /short lists of category values \(such as department names\) were sent\. No rows, and nothing from a personal data column\./)
  for (const payload of bar.work.payloads) for (const message of payload.messages) assert.ok(html.includes(escaped(message.content)))
  assert.match(html, /Copy SQL/)
})

test('table: one row needs no footnote; 5,000 rows draw 200 and say so; an empty cell is a dash', () => {
  const one = renderToStaticMarkup(h(DataTable, { table: tableOf([['HR', null]]), caption: 'Pay' }))
  assert.equal(words(one), 'Pay Dept Amount HR —')
  const many = renderToStaticMarkup(h(DataTable, { table: tableOf(Array.from({ length: 5000 }, (_, i) => [`D${i}`, -25000000 * i])), caption: 'Pay' }))
  assert.equal(many.match(/<tr/g).length, 201)
  assert.match(words(many), /Showing the first 200 rows\. The full result is longer\./)
  assert.match(many, /<th[^>]*text-right[^>]*>Amount/, 'numbers are right-aligned')
})

test('result view: KPI shows the display string; an empty result says so in a sentence', () => {
  assert.match(words(renderToStaticMarkup(h(ResultView, { chart: kpi.chart, table: kpi.table }))), /28\.6% Exits 2 Avg headcount 7/)
  const none = renderToStaticMarkup(h(ResultView, { chart: bar.chart, table: { ...bar.table, rows: [], display: [], row_count: 0 } }))
  assert.equal(words(none), 'The query ran and returned no rows.')
})

test('bar labels: a negative bar is labelled right of the zero line, never over the department name', () => {
  const label = barEndLabel('currency_inr')
  // Recharts describes a negative bar as starting at zero with a negative width.
  assert.match(renderToStaticMarkup(label({ x: 100, y: 10, width: -40, height: 20, value: -300000000 })), /<text x="106" y="20"[^>]*>-₹30\.00 Cr<\/text>/)
  assert.match(renderToStaticMarkup(label({ x: 100, y: 10, width: 40, height: 20, value: 99999.5 })), /<text x="146"[^>]*>₹99,999\.50<\/text>/)
  assert.equal(label({ x: 100, y: 10, width: 0, height: 20, value: null }), null, 'an empty cell has no label')
})

test('steps: a failed step is named as failed, in words a screen reader gets too', () => {
  const html = renderToStaticMarkup(h(StepList, { running: false, steps: [{ stage: 'guard', status: 'ok', detail: '' }, { stage: 'execute', status: 'failed', detail: 'The query took too long.' }] }))
  assert.match(words(html), /How it went: 2 steps, 1 failed .*Failed: Running the query: The query took too long\./)
})

test('thread: before the first question it offers the suggested questions and a labelled composer', () => {
  const html = renderToStaticMarkup(h(Thread, { sessionId: 's', catalog, onSessionExpired: noop }))
  for (const question of catalog.suggested_questions) assert.ok(words(html).includes(question))
  assert.match(html, /<label for="verity-question"/)
  assert.match(html, /<button type="submit" disabled=""/, 'nothing to ask yet')
  // Screen-reader-only text is absolutely positioned. If the scroller is not `relative`, that text is laid
  // out against the page, the page grows as tall as the conversation, and the header scrolls away.
  assert.match(html, /class="relative [^"]*overflow-y-auto/)
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
