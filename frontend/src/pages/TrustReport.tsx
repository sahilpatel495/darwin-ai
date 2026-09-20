// The Trust Report (`#/trust`): the product's proof, drawn as a ledger.
//
// How often Verity is right on a fixed set of test questions whose correct answers were computed
// independently of the app. It reads eval/report.json through GET /api/eval/report and only
// displays it; nothing is computed here beyond formatting, so the page can never disagree with
// the report file. The accuracy is the one Figure on the page — everything else is a ruled row.
import { useEffect, useState, type ReactNode } from 'react'
import { ApiError, getEvalReport } from '../api'
import { Banner, Button, EmptyState, Figure, RuledRow, Skeleton } from '../components/ui'
import { formatDuration, formatShare, humanize } from '../lib/format'
import type { EvalReport } from '../types'

type Load = { state: 'loading' } | { state: 'ready'; report: EvalReport } | { state: 'missing' } | { state: 'failed'; message: string; nextStep: string }

const LEVELS = ['high', 'medium', 'low'] as const
const th = 'border-b border-rule-strong bg-wash px-3 py-2 text-left type-small font-semibold whitespace-nowrap text-ink-soft'
const td = 'border-b border-rule px-3 py-2 align-top type-small'

function when(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

/** A section of the report: a rule, a title, then the evidence. No cards anywhere on this page. */
function Block({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <section className="mt-10 border-t border-rule pt-6">
      <h2 className="type-title text-ink">{title}</h2>
      {intro && <p className="mt-1 measure type-body text-ink-soft">{intro}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

/** A label and its share, with a thin bar between them. The bar is decoration; the number is read. */
function BarRow({ label, share, value }: { label: string; share: number; value: string }) {
  return (
    <RuledRow as="li" className="items-center">
      <span className="w-32 shrink-0 truncate type-small text-ink">{label}</span>
      <span aria-hidden className="h-2 min-w-0 flex-1 bg-wash">
        <span className="block h-2 bg-indigo" style={{ width: `${Math.max(0, Math.min(1, share)) * 100}%` }} />
      </span>
      <span className="w-14 shrink-0 text-right type-small text-ink tabular-nums">{value}</span>
    </RuledRow>
  )
}

/** A figure that is not the headline: named on the left, right-aligned on the right. */
function Line({ label, value }: { label: string; value: string }) {
  return (
    <RuledRow>
      <dt className="min-w-0 type-body text-ink">{label}</dt>
      <dd className="m-0 ml-auto shrink-0 type-body text-ink tabular-nums">{value}</dd>
    </RuledRow>
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
  // A run over the tuning questions only has no unseen questions; its file still says 0, and
  // "0% correct" would be read as a failure rather than as "not measured".
  const unseenMeasured = report.cases.some((c) => c.split === 'holdout')
  const cases = failedOnly ? report.cases.filter((c) => !c.passed) : report.cases
  return (
    <div>
      <div className="grid gap-x-12 gap-y-8 sm:grid-cols-[auto_minmax(0,22rem)] sm:items-end">
        <div>
          <h2 className="type-title text-ink-soft">Correct answers</h2>
          <Figure value={formatShare(report.accuracy)} className="mt-2" />
        </div>
        <dl className="m-0 border-t border-rule">
          <Line label="Correct on unseen questions" value={unseenMeasured ? formatShare(report.accuracy_holdout) : 'Not measured'} />
          <Line label="Trust score, from -1 to 1" value={report.trust_score.toFixed(2)} />
        </dl>
      </div>

      <p className="mt-6 measure type-small text-ink-soft">
        {report.total} test questions, run {report.runs} {report.runs === 1 ? 'time' : 'times'} with {report.model}. The correct answers were
        worked out separately from the app, from the clean source data. Generated {when(report.generated_at)}.
      </p>

      <div className="mt-6 measure space-y-3 type-body text-ink-soft">
        <p>
          Some of these questions were set aside at the start and never looked at while Verity was being tuned. Those are the ones worth
          reading: a high score on questions used for tuning only shows the tuning worked, while a similar score on the unseen ones suggests
          nothing was memorised. The trust score counts a wrong answer as worse than no answer, because that is how a wrong number behaves in
          a meeting.
        </p>
        <p>
          The rating on every answer is checked here too. It is only worth reading if answers rated high really are right more often than
          answers rated low, since that is what tells you which numbers to open the working on before you quote them.
        </p>
        <p>
          All of this runs against one made-up company. A full score means nothing has broken since the last run. It is not proof that Verity
          will be right on your files, which it has never seen.
        </p>
      </div>

      {Object.keys(report.by_category).length > 0 && (
        <Block title="Accuracy by type of question">
          <ul>
            {Object.entries(report.by_category).map(([category, accuracy]) => (
              <BarRow key={category} label={humanize(category)} share={accuracy} value={formatShare(accuracy)} />
            ))}
          </ul>
        </Block>
      )}

      <Block title="Is the confidence badge honest?" intro="Every answer carries a high, medium or low rating. This table checks whether the higher ratings really were right more often.">
        <div className="overflow-x-auto">
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
                  <td className={td}>{humanize(level)}</td>
                  <td className={`${td} text-right tabular-nums`}>{report.calibration[level].n}</td>
                  <td className={`${td} text-right tabular-nums`}>{report.calibration[level].n > 0 ? formatShare(report.calibration[level].accuracy) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 measure type-body text-ink-soft">{calibrationVerdict(report.calibration)}</p>
      </Block>

      <Block title="Speed and self-correction">
        <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['Typical answer time', formatDuration(report.p50_ms), 'Half of the answers arrive faster than this.'],
            ['Slow answer time', formatDuration(report.p95_ms), '19 in 20 answers arrive faster than this.'],
            ['Needed a repair', formatShare(report.repair_rate), 'The first query failed a check and was rewritten automatically.'],
            ['Second model agreed', report.crosscheck_agreement === null ? 'Not measured' : formatShare(report.crosscheck_agreement), 'A different model wrote its own query and got the same result.'],
          ].map(([label, value, help]) => (
            <div key={label} className="border-t border-rule pt-3">
              <dt className="type-small text-ink-soft">{label}</dt>
              <dd className="m-0 mt-1 type-statement text-ink tabular-nums">{value}</dd>
              <dd className="m-0 mt-1 type-small text-ink-soft">{help}</dd>
            </div>
          ))}
        </dl>
      </Block>

      {report.models.length > 0 && (
        <Block title="Models compared" intro="The model that writes the query was chosen by this test, not by reputation.">
          <div className="overflow-x-auto">
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
                      {m.model === report.model && <span className="text-ink-soft">, in use</span>}
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
        <label className="mb-3 flex w-fit cursor-pointer items-center gap-2 type-body text-ink">
          <input type="checkbox" checked={failedOnly} onChange={(e) => setFailedOnly(e.target.checked)} className="size-4 accent-(--color-indigo)" />
          Show failed only ({failures})
        </label>
        {cases.length === 0 ? (
          <p className="type-body text-ink-soft">{failedOnly ? 'No test question failed in this run.' : 'This report lists no individual questions.'}</p>
        ) : (
          <div className="max-h-[32rem] overflow-auto border-t border-rule" tabIndex={0} role="region" aria-label="Test questions">
            <table className="w-full border-collapse">
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
                      <span className="block type-small text-ink-soft">
                        {c.id}
                        {c.split === 'holdout' && ', unseen question'}
                        {c.expected_kind !== c.got_kind && `, expected ${c.expected_kind}, got ${c.got_kind}`}
                      </span>
                      {!c.passed && c.note && <span className="mt-1 block type-small text-red">{c.note}</span>}
                    </td>
                    <td className={`${td} whitespace-nowrap`}>{humanize(c.category)}</td>
                    <td className={`${td} font-medium whitespace-nowrap ${c.passed ? 'text-audit' : 'text-red'}`}>{c.passed ? 'Passed' : 'Failed'}</td>
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
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
      {/* No "back" link here: the header already shows "Back to questions" on this page. */}
      <h1 className="type-statement text-ink">Trust Report</h1>
      <p className="mt-1 mb-8 measure type-body text-ink-soft">
        How often Verity gets it right, measured on a fixed set of test questions with known correct answers.
      </p>

      {load.state === 'loading' && (
        <div role="status" className="space-y-3">
          <p className="type-body text-ink-soft">Reading the latest accuracy test…</p>
          <Skeleton className="h-12 w-40" />
          <Skeleton className="h-4 w-full max-w-md" />
          <Skeleton className="h-4 w-full max-w-sm" />
        </div>
      )}
      {load.state === 'ready' && <Report report={load.report} />}
      {load.state === 'missing' && (
        <>
          <EmptyState>
            The accuracy test has not been run on this installation, so there is nothing to show here yet. Your own questions still work as
            normal, and every answer still shows how it was worked out.
          </EmptyState>
          <p className="mt-6 measure type-body text-ink-soft">If you run this installation, create the report from the project folder with:</p>
          <pre className="mt-2 overflow-x-auto border border-rule bg-wash p-3 type-code text-ink">PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split dev</pre>
        </>
      )}
      {load.state === 'failed' && (
        <Banner tone="error" nextStep={load.nextStep} action={<Button onClick={() => setAttempt((n) => n + 1)}>Try again</Button>}>
          {load.message}
        </Banner>
      )}
    </div>
  )
}
