// Seam: the shell shows this page when location.hash === '#/trust'. Owned by frontend-thread.
//
// The Trust Report is the product's proof: how often Verity is right on a fixed set of test
// questions whose correct answers were computed independently of the app. It reads
// eval/report.json through GET /api/eval/report and only displays it; nothing is computed here
// beyond formatting, so the page can never disagree with the report file.
import { useEffect, useState, type ReactNode } from 'react'
import { ApiError, getEvalReport } from '../api'
import ErrorNotice from '../components/answer/ErrorNotice'
import { formatDuration, formatShare, humanize } from '../lib/format'
import type { EvalReport } from '../types'

type Load = { state: 'loading' } | { state: 'ready'; report: EvalReport } | { state: 'missing' } | { state: 'failed'; message: string; nextStep: string }

const LEVELS = ['high', 'medium', 'low'] as const
const card = 'rounded-card border border-line bg-surface p-4 sm:p-5'
const th = 'border-b border-line bg-sunken px-3 py-2 text-left font-medium whitespace-nowrap text-ink-soft'
const td = 'border-b border-line px-3 py-2 align-top'

function when(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

function Stat({ label, value, help }: { label: string; value: string; help: string }) {
  return (
    <div className={card}>
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight text-ink tabular-nums">{value}</p>
      <p className="mt-2 text-xs leading-relaxed text-ink-soft">{help}</p>
    </div>
  )
}

function Block({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <section className={card}>
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      {intro && <p className="mt-1 max-w-prose text-sm text-ink-soft">{intro}</p>}
      <div className="mt-4">{children}</div>
    </section>
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
    : 'In this run the badge was not well ordered: a lower rating was right more often than a higher one. Treat the badge with care.'
}

/** Exported so render.test.mjs can draw it without a network call. */
export function Report({ report }: { report: EvalReport }) {
  const [failedOnly, setFailedOnly] = useState(false)
  const failures = report.cases.filter((c) => !c.passed).length
  const cases = failedOnly ? report.cases.filter((c) => !c.passed) : report.cases
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-soft">
        {report.total} test questions, run {report.runs} {report.runs === 1 ? 'time' : 'times'} with {report.model}. Generated {when(report.generated_at)}.
      </p>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Correct answers" value={formatShare(report.accuracy)} help="Share of test questions answered correctly. The correct answers were worked out separately from the app, from the clean source data." />
        <Stat label="Correct on unseen questions" value={formatShare(report.accuracy_holdout)} help="Questions that were kept aside and never used while tuning. A figure close to the share of correct answers means the result is not memorised." />
        <Stat label="Trust score" value={report.trust_score.toFixed(2)} help="Plus 1 for a correct answer, 0 for honestly saying it cannot answer, minus 1 for a wrong answer. It ranges from -1 to 1. A wrong answer costs more than no answer." />
      </div>

      {Object.keys(report.by_category).length > 0 && (
        <Block title="Accuracy by type of question">
          <ul className="space-y-2">
            {Object.entries(report.by_category).map(([category, accuracy]) => (
              <li key={category} className="grid grid-cols-[minmax(0,9rem)_1fr_3.5rem] items-center gap-3 text-sm">
                <span className="truncate text-ink">{humanize(category)}</span>
                <span className="h-3 rounded-r bg-sunken" aria-hidden="true">
                  <span className="block h-3 rounded-r bg-series-1" style={{ width: `${Math.max(0, Math.min(1, accuracy)) * 100}%` }} />
                </span>
                <span className="text-right text-ink tabular-nums">{formatShare(accuracy)}</span>
              </li>
            ))}
          </ul>
        </Block>
      )}

      <Block
        title="Is the confidence badge honest?"
        intro="Every answer carries a High, Medium or Low badge. The badge is only useful if High answers really are right more often than Low ones, so that you know which numbers to double-check before a meeting. This table checks exactly that."
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
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
                  <td className={td}>{humanize(level)}</td>
                  <td className={`${td} text-right tabular-nums`}>{report.calibration[level].n}</td>
                  <td className={`${td} text-right tabular-nums`}>{report.calibration[level].n > 0 ? formatShare(report.calibration[level].accuracy) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm text-ink-soft">{calibrationVerdict(report.calibration)}</p>
      </Block>

      <Block title="Speed and self-correction">
        <dl className="grid gap-4 text-sm sm:grid-cols-4">
          {[
            ['Typical answer time', formatDuration(report.p50_ms), 'Half of the answers arrive faster than this.'],
            ['Slow answer time', formatDuration(report.p95_ms), '19 in 20 answers arrive faster than this.'],
            ['Needed a repair', formatShare(report.repair_rate), 'The first SQL failed a check and was rewritten automatically.'],
            ['Second model agreed', report.crosscheck_agreement === null ? 'Not measured' : formatShare(report.crosscheck_agreement), 'A different model wrote its own SQL and got the same result.'],
          ].map(([label, value, help]) => (
            <div key={label}>
              <dt className="text-ink-soft">{label}</dt>
              <dd className="m-0 mt-0.5 text-xl font-semibold text-ink tabular-nums">{value}</dd>
              <dd className="m-0 mt-1 text-xs text-ink-soft">{help}</dd>
            </div>
          ))}
        </dl>
      </Block>

      {report.models.length > 0 && (
        <Block title="Models compared" intro="The model that writes the SQL was chosen by this test, not by reputation.">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
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
                      {m.model === report.model && <span className="ml-2 rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent-ink">in use</span>}
                    </td>
                    <td className={`${td} text-right tabular-nums`}>{formatShare(m.accuracy)}</td>
                    <td className={`${td} text-right tabular-nums`}>{formatDuration(m.p50_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Block>
      )}

      <Block title="Every test question" intro="Failures are listed, not hidden. Each one says what went wrong.">
        <label className="mb-3 flex w-fit cursor-pointer items-center gap-2 text-sm text-ink">
          <input type="checkbox" checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)} className="size-4 accent-(--color-accent)" />
          Show failed only ({failures})
        </label>
        {cases.length === 0 ? (
          <p className="text-sm text-ink-soft">{failedOnly ? 'No test question failed in this run.' : 'This report lists no individual questions.'}</p>
        ) : (
          <div className="max-h-[32rem] overflow-auto rounded-lg border border-line" tabIndex={0} role="region" aria-label="Test questions">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  {['Question', 'Type', 'Result', 'Badge', 'Time', 'Repairs'].map((heading, i) => (
                    <th key={heading} scope="col" className={`${th} sticky top-0 ${i >= 4 ? 'text-right' : ''}`}>{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id}>
                    <td className={`${td} min-w-[16rem]`}>
                      <span className="text-ink">{c.question}</span>
                      <span className="block text-xs text-ink-soft">
                        {c.id}
                        {c.split === 'holdout' && ', unseen question'}
                        {c.expected_kind !== c.got_kind && `, expected ${c.expected_kind}, got ${c.got_kind}`}
                      </span>
                      {!c.passed && c.note && <span className="mt-1 block text-xs text-bad">{c.note}</span>}
                    </td>
                    <td className={`${td} whitespace-nowrap`}>{humanize(c.category)}</td>
                    <td className={`${td} font-medium whitespace-nowrap ${c.passed ? 'text-good' : 'text-bad'}`}>{c.passed ? 'Passed' : 'Failed'}</td>
                    <td className={`${td} whitespace-nowrap`}>{c.confidence ? humanize(c.confidence) : '—'}</td>
                    <td className={`${td} text-right whitespace-nowrap tabular-nums`}>{formatDuration(c.latency_ms)}</td>
                    <td className={`${td} text-right tabular-nums`}>{c.repairs}</td>
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
        setLoad({ state: 'failed', message: known ? error.message : 'The Trust Report could not be read.', nextStep: known ? error.nextStep : 'Try again in a moment.' })
      })
    return () => {
      current = false
    }
  }, [attempt])

  return (
    // A div, not <main>: the shell already wraps this page in the document's one <main>.
    <div className="mx-auto w-full max-w-5xl px-4 py-6">
      <a href="#/" className="text-sm font-medium text-accent-ink underline">
        Back to your data
      </a>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink">Trust Report</h1>
      <p className="mt-1 mb-5 max-w-prose text-sm text-ink-soft">How often Verity gets it right, measured on a fixed set of test questions with known correct answers.</p>

      {load.state === 'loading' && (
        <div aria-busy="true" aria-label="Loading the Trust Report" className="grid gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-card border border-line bg-sunken" />
          ))}
        </div>
      )}
      {load.state === 'ready' && <Report report={load.report} />}
      {load.state === 'missing' && (
        <div className={card}>
          <h2 className="text-base font-semibold text-ink">No report has been generated yet</h2>
          <p className="mt-1 max-w-prose text-sm text-ink-soft">
            The accuracy test has not been run on this installation, so there is nothing to show. Your own questions still work as normal, and every answer still shows how it was worked out.
          </p>
          <p className="mt-3 max-w-prose text-sm text-ink-soft">If you run this installation, create the report from the project folder with:</p>
          <pre className="mt-2 overflow-x-auto rounded-md bg-sunken p-3 font-mono text-xs text-ink">PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split dev</pre>
        </div>
      )}
      {load.state === 'failed' && <ErrorNotice message={load.message} nextStep={load.nextStep} onRetry={() => setAttempt((n) => n + 1)} />}
    </div>
  )
}
