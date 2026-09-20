// `#/trust` (§6, §7): the product's proof, in the marketing language rather than a spreadsheet.
//
// How often DarwinLens is right on a fixed set of test questions whose correct answers were worked
// out independently of the app. It reads eval/report.json through GET /api/eval/report and only
// displays it; nothing is computed here beyond formatting, so the page can never disagree with the
// report file. Failures are listed, not hidden — a proof page that only shows wins is an advert.

import { useEffect, useState, type ReactNode } from 'react'
import { ApiError, getEvalReport } from '../api'
import { EXPLAIN } from '../components/education/explain'
import { AuroraBackdrop } from '../components/graphics'
import { Badge, Banner, Button, Card, EmptyState, Skeleton, StatTile, WhatsThis, cx } from '../components/ui'
import { formatDuration, formatShare, humanize } from '../lib/format'
import { HOME, HOW } from '../lib/route'
import type { EvalReport } from '../types'

type Load = { state: 'loading' } | { state: 'ready'; report: EvalReport } | { state: 'missing' } | { state: 'failed'; message: string; nextStep: string }

const LEVELS = ['high', 'medium', 'low'] as const

// The report's own category keys are written for the engineer who runs the test. "joins" is not a
// word this product uses in front of an analyst (§12), so the four known keys get their sentence
// and anything new falls back to being sentence-cased.
const CATEGORY_WORDS: Record<string, string> = {
  totals: 'Totals and averages',
  joins: 'Questions that span two files',
  hr_metrics: 'HR measures such as attrition',
  unanswerable: 'Questions the data cannot answer',
}
const categoryLabel = (key: string): string => CATEGORY_WORDS[key] ?? humanize(key)

const th = 'border-b border-hairline-soft bg-surface-soft px-4 py-3 text-left text-body-sm font-bold whitespace-nowrap text-ink-deep'
const td = 'border-b border-hairline-soft px-4 py-3 align-top text-body-sm text-ink'

function when(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

/** One part of the report: its title, the reason it is here, then the evidence. */
function Block({ title, intro, aside, children }: { title: string; intro?: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-16">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <h2 className="text-heading-lg text-ink-deep">{title}</h2>
        {aside}
      </div>
      {intro && <p className="mt-3 measure text-body-md text-slate">{intro}</p>}
      <div className="mt-6">{children}</div>
    </section>
  )
}

/** A figure with its name above it: a tile whose label came second is a number with no meaning. */
function Tile({ label, value, help, animate }: { label: string; value: string; help: string; animate?: boolean }) {
  return (
    <Card className="flex flex-col justify-between">
      <p className="text-body-sm font-bold text-ink-deep">{label}</p>
      <StatTile value={value} label={help} animate={animate} className="mt-4" />
    </Card>
  )
}

/** The bars draw once, on arrival (§4): the comparison is the point, so it is what moves. */
function Bars({ rows }: { rows: [string, number][] }) {
  const [drawn, setDrawn] = useState(false)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setDrawn(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  return (
    <ul className="space-y-3">
      {rows.map(([label, share]) => (
        <li key={label} className="flex items-center gap-4">
          <span className="w-40 shrink-0 text-body-md text-ink sm:w-64">{label}</span>
          <span aria-hidden className="h-3 min-w-0 flex-1 overflow-hidden rounded-full bg-surface-soft">
            <span
              className="block h-full rounded-full bg-chart-1 transition-[width] duration-[var(--dur-long)] ease-[var(--ease-out)]"
              style={{ width: `${(drawn ? Math.max(0, Math.min(1, share)) : 0) * 100}%` }}
            />
          </span>
          <span className="w-16 shrink-0 text-right text-body-md font-bold text-ink-deep tnum">{formatShare(share)}</span>
        </li>
      ))}
    </ul>
  )
}

/** The server sends eval/report.json as it is on disk, unchecked. A file from an older version
 *  or a half-written one must show a plain message, not crash the page while it is being drawn. */
export function isReadable(report: unknown): report is EvalReport {
  const r = (report ?? {}) as Partial<EvalReport>
  const isRecord = (value: unknown) => typeof value === 'object' && value !== null
  return Array.isArray(r.cases) && Array.isArray(r.models) && isRecord(r.by_category) && isRecord(r.calibration) && typeof r.trust_score === 'number'
}

const UNREADABLE = { state: 'failed', message: 'The report file is not in a format this page can read.', nextStep: 'Run the accuracy test again to create a fresh report, then try again.' } as const

/** The badge is honest when answers rated higher are right at least as often. */
function calibrationVerdict(calibration: EvalReport['calibration']): string {
  const rates = LEVELS.filter((level) => (calibration[level]?.n ?? 0) > 0).map((level) => calibration[level].accuracy)
  if (rates.length < 2) return 'There are not enough rated answers in this run to judge the badge.'
  const ordered = rates.every((rate, i) => i === 0 || rate <= rates[i - 1])
  return ordered
    ? 'In this run the badge behaved as it should: higher confidence went with higher accuracy.'
    : 'In this run the badge was not well ordered — a lower rating was right more often than a higher one. Treat the badge with care until the next run.'
}

/** Exported so a render test can draw it without a network call. */
export function Report({ report }: { report: EvalReport }) {
  const [failedOnly, setFailedOnly] = useState(false)
  const failures = report.cases.filter((c) => !c.passed).length
  // A run over the tuning questions only has no unseen questions; its file still says 0, and
  // "0% correct" would be read as a failure rather than as "not measured".
  const unseenMeasured = report.cases.some((c) => c.split === 'holdout')
  const cases = failedOnly ? report.cases.filter((c) => !c.passed) : report.cases

  return (
    <div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Tile label="Correct answers" value={formatShare(report.accuracy)} help="Across every test question in this run." animate />
        <Tile
          label="Correct on unseen questions"
          value={unseenMeasured ? formatShare(report.accuracy_holdout) : 'Not measured'}
          help="Questions set aside at the start and never looked at while DarwinLens was tuned."
          animate={unseenMeasured}
        />
        <Tile label="Trust score, from −1 to 1" value={report.trust_score.toFixed(2)} help="A wrong answer counts as worse than no answer." animate />
      </div>

      {/* The honest sentence: what was measured, with what, and when. It sits directly under the
          three headline figures because it is the caveat on all three. */}
      <p className="mt-6 measure text-body-md text-slate">
        {report.total} test questions, run {report.runs} {report.runs === 1 ? 'time' : 'times'} with {report.model}. The correct answers were
        worked out separately from the app, from the clean source data. These figures were measured on {when(report.generated_at)} and have
        not been recalculated since.
      </p>

      <Card tone="soft" radius="xxl" className="mt-10">
        <h2 className="text-heading-sm text-ink-deep">What this does and does not prove</h2>
        <div className="mt-4 measure space-y-4 text-body-md text-slate">
          <p>
            Some of these questions were set aside at the start and never looked at while DarwinLens was being tuned. Those are the ones worth
            reading: a high score on questions used for tuning only shows the tuning worked, while a similar score on the unseen ones suggests
            nothing was memorised. The trust score counts a wrong answer as worse than no answer, because that is how a wrong number behaves in
            a meeting.
          </p>
          <p>
            The rating on every answer is checked here too. It is only worth reading if answers rated high really are right more often than
            answers rated low, since that is what tells you which numbers to open the working on before you quote them.
          </p>
          <p className="text-ink-deep">
            All of this runs against one made-up company. A full score means nothing has broken since the last run. It is not proof that
            DarwinLens will be right on your files, which it has never seen.
          </p>
        </div>
      </Card>

      {Object.keys(report.by_category).length > 0 && (
        <Block title="Accuracy by type of question" intro="Where it is strong, and where it is not.">
          <Bars rows={Object.entries(report.by_category).map(([category, accuracy]) => [categoryLabel(category), accuracy])} />
        </Block>
      )}

      <Block
        title="Is the confidence badge honest?"
        intro="Every answer carries a high, medium or low rating. This checks whether the higher ratings really were right more often."
        aside={<WhatsThis {...EXPLAIN.confidence} align="right" />}
      >
        <div className="overflow-x-auto rounded-xl border border-hairline-soft">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th scope="col" className={th}>Badge</th>
                <th scope="col" className={`${th} text-right`}>Answers</th>
                <th scope="col" className={`${th} text-right`}>Correct</th>
              </tr>
            </thead>
            <tbody>
              {LEVELS.filter((level) => report.calibration[level]).map((level) => (
                <tr key={level}>
                  <td className={td}>
                    <Badge level={level} />
                  </td>
                  <td className={`${td} text-right tnum`}>{report.calibration[level].n}</td>
                  <td className={`${td} text-right tnum`}>{report.calibration[level].n > 0 ? formatShare(report.calibration[level].accuracy) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-5 measure text-body-md text-ink-deep">{calibrationVerdict(report.calibration)}</p>
      </Block>

      <Block title="Speed and self-correction">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {(
            [
              ['Typical answer time', formatDuration(report.p50_ms), 'Half of the answers arrive faster than this.'],
              ['Slow answer time', formatDuration(report.p95_ms), '19 in 20 answers arrive faster than this.'],
              ['Needed a repair', formatShare(report.repair_rate), 'The first query failed a check and was rewritten automatically.'],
              [
                'Second model agreed',
                report.crosscheck_agreement === null ? 'Not measured' : formatShare(report.crosscheck_agreement),
                'A different model wrote its own query and got the same result.',
              ],
            ] as [string, string, string][]
          ).map(([label, value, help]) => (
            <Tile key={label} label={label} value={value} help={help} />
          ))}
        </div>
      </Block>

      {report.models.length > 0 && (
        <Block title="Models compared" intro="The model that writes the query was chosen by this test, not by reputation.">
          <div className="overflow-x-auto rounded-xl border border-hairline-soft">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th scope="col" className={th}>Model</th>
                  <th scope="col" className={`${th} text-right`}>Correct</th>
                  <th scope="col" className={`${th} text-right`}>Typical time</th>
                </tr>
              </thead>
              <tbody>
                {report.models.map((m) => (
                  <tr key={m.model}>
                    <td className={td}>
                      {m.model}
                      {m.model === report.model && <span className="text-steel">, in use</span>}
                    </td>
                    <td className={`${td} text-right tnum`}>{formatShare(m.accuracy)}</td>
                    <td className={`${td} text-right tnum`}>{formatDuration(m.p50_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Block>
      )}

      <Block title="The challenge set" intro="Every question the test asks, and what came back. Failures are listed, not hidden — each one says what went wrong.">
        <label className="mb-4 flex w-fit cursor-pointer items-center gap-2.5 text-body-md text-ink">
          <input type="checkbox" checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)} className="size-4 accent-(--color-primary)" />
          Show failures only ({failures})
        </label>
        {cases.length === 0 ? (
          <p className="text-body-md text-slate">{failedOnly ? 'No test question failed in this run.' : 'This report lists no individual questions.'}</p>
        ) : (
          <div className="max-h-[32rem] overflow-auto rounded-xl border border-hairline-soft" tabIndex={0} role="region" aria-label="Test questions">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  {['Question', 'Type', 'Result', 'Badge', 'Time', 'Repairs'].map((heading, i) => (
                    <th key={heading} scope="col" className={cx(th, 'sticky top-0 z-10', i >= 4 && 'text-right')}>
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id}>
                    <td className={`${td} min-w-[16rem]`}>
                      <span className="text-ink-deep">{c.question}</span>
                      <span className="block text-body-sm text-steel">
                        {c.id}
                        {c.split === 'holdout' && ', unseen question'}
                        {c.expected_kind !== c.got_kind && `, expected ${c.expected_kind}, got ${c.got_kind}`}
                      </span>
                      {!c.passed && c.note && <span className="mt-1 block text-body-sm text-critical">{c.note}</span>}
                    </td>
                    <td className={`${td} whitespace-nowrap`}>{categoryLabel(c.category)}</td>
                    <td className={cx(td, 'font-bold whitespace-nowrap', c.passed ? 'text-success' : 'text-critical')}>{c.passed ? 'Passed' : 'Failed'}</td>
                    <td className={`${td} whitespace-nowrap`}>{c.confidence ? humanize(c.confidence) : '—'}</td>
                    <td className={`${td} text-right whitespace-nowrap tnum`}>{formatDuration(c.latency_ms)}</td>
                    <td className={`${td} text-right tnum`}>{c.repairs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Block>
    </div>
  )
}

export default function TrustReport() {
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let current = true
    setLoad({ state: 'loading' })
    getEvalReport()
      .then((report) => current && setLoad(isReadable(report) ? { state: 'ready', report } : UNREADABLE))
      .catch((error: unknown) => {
        if (!current) return
        if (error instanceof ApiError && error.status === 404) return setLoad({ state: 'missing' })
        const known = error instanceof ApiError
        setLoad({ state: 'failed', message: known ? error.message : 'The trust report could not be read.', nextStep: known ? error.nextStep : 'Try again in a moment.' })
      })
    return () => {
      current = false
    }
  }, [attempt])

  return (
    // A div, not <main>: the shell already wraps this page in the document's one <main>.
    <div>
      <div className="relative isolate overflow-hidden">
        <AuroraBackdrop intensity="panel" />
        <div className="relative mx-auto w-full max-w-[1120px] px-4 pt-12 pb-10 sm:px-6 sm:pt-16">
          <h1 className="measure text-display-lg text-ink-deep">How often is it right?</h1>
          <p className="mt-5 measure text-subtitle-md text-slate">
            DarwinLens is scored on a fixed set of test questions whose correct answers were worked out separately, from
            the clean source data. This page is that score, including the questions it got wrong.
          </p>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[1120px] px-4 pb-20 sm:px-6">
        {load.state === 'loading' && (
          <div role="status" aria-label="Reading the latest accuracy test">
            <p className="text-body-md text-slate">Reading the latest accuracy test…</p>
            <div aria-hidden className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <Card key={i}>
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="mt-4 h-10 w-24" />
                  <Skeleton className="mt-2 h-4 w-full" />
                </Card>
              ))}
            </div>
          </div>
        )}
        {load.state === 'ready' && <Report report={load.report} />}
        {load.state === 'missing' && (
          <>
            <EmptyState glyph="shield" title="No accuracy test has been run here">
              Your own questions still work as normal, and every answer still shows how it was worked out.
            </EmptyState>
            <p className="mt-8 measure text-body-md text-slate">If you run this installation, create the report from the project folder with:</p>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-soft p-4 text-code text-ink">
              PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split dev
            </pre>
          </>
        )}
        {load.state === 'failed' && (
          <Banner tone="error" nextStep={load.nextStep} action={<Button onClick={() => setAttempt((n) => n + 1)}>Try again</Button>}>
            {load.message}
          </Banner>
        )}

        <Card radius="xxxl" tone="soft" className="mt-16 flex flex-wrap items-center justify-between gap-6">
          <div>
            <h2 className="text-heading-sm text-ink-deep">Where these numbers come from</h2>
            <p className="mt-2 measure text-body-md text-slate">
              The How page walks through what the AI is given and what is held back, column by column.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a
              href={HOW}
              className="press inline-flex h-11 items-center rounded-full bg-ink-deep px-[30px] text-button-md text-white no-underline hover:bg-ink"
            >
              How DarwinLens works
            </a>
            <a
              href={HOME}
              className="press inline-flex h-11 items-center rounded-full border-2 border-ink-deep px-7 text-button-md text-ink-deep no-underline hover:bg-canvas"
            >
              Open DarwinLens
            </a>
          </div>
        </Card>
      </div>
    </div>
  )
}
