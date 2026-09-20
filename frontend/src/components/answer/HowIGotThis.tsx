// "How I got this": the working behind an answer, in the order someone would check it.
// Everything here is rendered as plain text. SQL, prompts and error messages can contain text
// from a customer's file, so nothing is ever treated as HTML or markdown.
import { useState, type ReactNode } from 'react'
import type { Attempt, ModelPayload, TableProfile, Work } from '../../types'
import { formatDuration } from '../../lib/format'
import { labelOf } from '../../lib/tables'

const PURPOSE: Record<ModelPayload['purpose'], string> = {
  generate: 'Writing the SQL',
  crosscheck: 'Cross-check by a second model',
  repair: 'Repairing the SQL',
  narrate: 'Phrasing the answer',
}

const ATTEMPT_REASON: Record<Attempt['reason'], string> = {
  initial: 'First attempt',
  sql_error: 'Retry after the database reported an error',
  guard_rejected: 'Retry after the safety check rejected the SQL',
  empty_result: 'Retry after a result that came back empty',
  fan_out: 'Retry to stop rows being counted twice in a join',
  period_missing: 'Retry to filter on the period the question names',
}

const ROLE: Record<string, string> = { system: 'Instructions (system)', user: 'Request (user)', assistant: 'Reply (assistant)' }

const code = 'overflow-x-auto rounded-md bg-sunken p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap break-words text-ink'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line py-3 first:border-t-0 first:pt-0">
      <h4 className="mb-1.5 text-sm font-medium text-ink">{title}</h4>
      <div className="text-sm text-ink-soft">{children}</div>
    </section>
  )
}

function SqlBlock({ sql }: { sql: string }) {
  const [copied, setCopied] = useState<'idle' | 'copied' | 'failed'>('idle')
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql)
      setCopied('copied')
    } catch {
      setCopied('failed') // clipboard is blocked on plain http and in some embedded views
    }
    setTimeout(() => setCopied('idle'), 2500)
  }
  return (
    <div>
      <pre className={code}>{sql}</pre>
      <button type="button" onClick={copy} className="mt-1.5 rounded-md border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink hover:bg-sunken">
        <span aria-live="polite">{copied === 'copied' ? 'Copied' : copied === 'failed' ? 'Could not copy. Select the text instead.' : 'Copy SQL'}</span>
      </button>
    </div>
  )
}

function Payload({ payload }: { payload: ModelPayload }) {
  return (
    <details className="rounded-md border border-line">
      <summary className="cursor-pointer px-3 py-2 text-sm text-ink">
        {PURPOSE[payload.purpose]}
        <span className="text-ink-soft">
          {' '}
          with {payload.model} on {payload.provider}, {payload.cached ? 'reused from an earlier identical request' : formatDuration(payload.latency_ms)}
        </span>
      </summary>
      <div className="space-y-2 border-t border-line p-3">
        {payload.purpose === 'narrate' && (
          <p className="text-xs text-ink-soft">This step also received the computed result as formatted text, with personal data replaced by placeholders, so it could phrase the answer.</p>
        )}
        {payload.messages.map((message, i) => (
          <div key={i}>
            <p className="mb-1 text-xs font-medium text-ink-soft">{ROLE[message.role] ?? message.role}</p>
            <pre className={code}>{message.content}</pre>
          </div>
        ))}
      </div>
    </details>
  )
}

const CROSS_CHECK: Record<Work['cross_check']['status'], string> = {
  agreed: 'A second model wrote its own SQL and reached the same result.',
  disagreed: 'A second model wrote its own SQL and reached a different result.',
  unavailable: 'The second model could not be reached, so this answer was not cross-checked.',
  skipped: '',
}

/** True when there is any working to show. A clarifying question asked before any model call
 *  has none, and an empty panel would only look broken. */
export const hasWork = (work: Work): boolean => Boolean(work.sql || work.reading || work.interpretation || work.plan.length || work.payloads.length || work.attempts.length)

export default function HowIGotThis({ work, tables }: { work: Work; tables: TableProfile[] }) {
  const reading = work.reading || work.interpretation
  const totalMs = Object.values(work.timings_ms).reduce((sum, ms) => sum + ms, 0)
  return (
    <details className="rounded-card border border-line">
      <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-accent-ink select-none">How I got this</summary>
      <div className="border-t border-line px-4 py-3">
        {reading && <Section title="How I read your question">{reading}</Section>}

        {work.plan.length > 0 && (
          <Section title="Plan">
            <ol className="list-decimal space-y-0.5 pl-5">
              {work.plan.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </Section>
        )}

        {work.tables_used.length > 0 && (
          <Section title="Data used">
            {work.tables_used.map((name) => labelOf(name, tables)).join(', ')}. {work.rows_scanned.toLocaleString('en-IN')} rows read by the database.
          </Section>
        )}

        {work.assumptions.length > 0 && (
          <Section title="Assumptions">
            <ul className="list-disc space-y-0.5 pl-5">
              {work.assumptions.map((assumption, i) => (
                <li key={i}>{assumption}</li>
              ))}
            </ul>
          </Section>
        )}

        {work.sql && (
          <Section title="SQL">
            <details>
              <summary className="cursor-pointer text-accent-ink">Show the query that produced this answer</summary>
              <div className="mt-2">
                <SqlBlock sql={work.sql} />
              </div>
            </details>
          </Section>
        )}

        {work.cross_check.status !== 'skipped' && (
          <Section title="Cross-check">
            {/* One sentence, not two: the server's detail repeats ours, except on a disagreement,
                where it adds what differed. When the second model failed, its detail is an error
                class name, which is for the server log, not for the analyst. */}
            <p>
              {work.cross_check.status === 'disagreed' && work.cross_check.detail ? work.cross_check.detail : CROSS_CHECK[work.cross_check.status]}
              {work.cross_check.model && ` Model: ${work.cross_check.model}.`}
            </p>
            {work.cross_check.sql && (
              <details className="mt-2">
                <summary className="cursor-pointer text-accent-ink">Show the second model's query</summary>
                <div className="mt-2">
                  <SqlBlock sql={work.cross_check.sql} />
                </div>
              </details>
            )}
          </Section>
        )}

        {work.attempts.length > 0 && (
          <Section title={`Attempts (${work.attempts.length})`}>
            <ol className="space-y-3">
              {work.attempts.map((attempt, i) => (
                <li key={i}>
                  <p className="mb-1 text-ink">
                    {i + 1}. {ATTEMPT_REASON[attempt.reason]} <span className="text-ink-soft">({attempt.model})</span>
                  </p>
                  <pre className={code}>{attempt.sql}</pre>
                  {attempt.error && <p className="mt-1 text-warn">This attempt failed: {attempt.error}</p>}
                </li>
              ))}
            </ol>
          </Section>
        )}

        {work.payloads.length > 0 && (
          <Section title="What the model saw">
            <p className="mb-2 font-medium text-ink">
              Column names, types, statistics and short lists of category values (such as department names) were sent. No rows, and nothing from a personal data column.
            </p>
            <div className="space-y-2">
              {work.payloads.map((payload, i) => (
                <Payload key={i} payload={payload} />
              ))}
            </div>
          </Section>
        )}

        {(work.cached || totalMs > 0) && (
          <p className="border-t border-line pt-3 text-xs text-ink-soft">
            {work.cached ? 'Same question on the same data as before, so the saved answer was returned.' : `Answered in ${formatDuration(totalMs)}.`}
          </p>
        )}
      </div>
    </details>
  )
}
