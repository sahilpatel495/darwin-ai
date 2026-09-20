// "How I got this": the working behind an answer, in the order someone would check it. The
// statement above it makes a claim; this is where the claim is audited. It opens with the route
// the answer took (§12) and then gives every step of it in full.
//
// Everything here is rendered as plain text. SQL, prompts and error messages can contain text
// from a customer's file, so nothing is ever treated as HTML or markdown.
import { useState, type HTMLAttributes, type ReactNode } from 'react'
import { Button, cx } from '../ui'
import type { Attempt, ModelPayload, TableProfile, Work } from '../../types'
import { formatDuration } from '../../lib/format'
import { labelOf } from '../../lib/tables'
import { flowNodes, type FlowNode, type FlowTone } from './flow'

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
}

const ROLE: Record<string, string> = { system: 'Instructions (system)', user: 'Request (user)', assistant: 'Reply (assistant)' }

// Mono is for SQL and prompts only — never for a data label (§3).
const code = 'overflow-x-auto rounded-input bg-surface-2 p-3 type-code whitespace-pre-wrap break-words text-ink'
const quietLink = 'cursor-pointer text-blue-ink underline decoration-blue-ink/40 underline-offset-2 hover:decoration-current'

// --- The route the answer took ---------------------------------------------

const TONE: Record<FlowTone, string> = {
  done: 'bg-green-soft text-green-ink',
  warn: 'bg-amber-soft text-amber-ink',
  failed: 'bg-red-soft text-red-ink',
  idle: 'bg-fill text-ink-2',
}

/** The loop a rewritten query took, drawn on the node it went back to. */
function Loop({ times }: { times: number }) {
  return (
    <span className="mt-1 inline-flex items-center gap-1 rounded-pill bg-amber-soft px-2 py-0.5 type-micro text-amber-ink">
      <svg aria-hidden width="12" height="12" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 7.5a6.5 6.5 0 1 0 .9 5" />
        <path d="M16.5 3v4.5H12" />
      </svg>
      {times === 1 ? 'Rewritten once' : `Rewritten ${times} times`}
    </span>
  )
}

function Flow({ nodes }: { nodes: FlowNode[] }) {
  return (
    <ol className="flex flex-wrap items-stretch gap-1.5">
      {nodes.map((node, i) => (
        <li key={node.id} className="flex items-center gap-1.5">
          <span className={cx('flex flex-col items-start rounded-card px-2.5 py-1.5', TONE[node.tone])}>
            <span className="type-micro font-semibold">{node.label}</span>
            {node.note && <span className="type-micro opacity-80">{node.note}</span>}
            {node.loops > 0 && <Loop times={node.loops} />}
          </span>
          {i < nodes.length - 1 && <span aria-hidden className="h-px w-3 shrink-0 bg-line" />}
        </li>
      ))}
    </ol>
  )
}

// --- The sections under it --------------------------------------------------

// `data-*` is spelled out because HTMLAttributes only allows it on JSX itself, not on a prop type.
type SectionProps = { title: string; children: ReactNode } & HTMLAttributes<HTMLElement> & { [key: `data-${string}`]: string }

function Section({ title, children, ...rest }: SectionProps) {
  return (
    <section className="border-t border-line-soft py-3 first:border-t-0 first:pt-0" {...rest}>
      <h4 className="mb-1.5 type-small font-semibold text-ink">{title}</h4>
      <div className="type-small text-ink-2">{children}</div>
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
      <Button size="sm" onClick={copy} className="mt-2">
        <span aria-live="polite">{copied === 'copied' ? 'Copied' : copied === 'failed' ? 'Could not copy. Select the text instead.' : 'Copy SQL'}</span>
      </Button>
    </div>
  )
}

function Payload({ payload }: { payload: ModelPayload }) {
  return (
    <details className="border-t border-line-soft pt-2 first:border-t-0 first:pt-0">
      <summary className="cursor-pointer type-small text-ink">
        {PURPOSE[payload.purpose]}
        <span className="text-ink-2">
          {' '}
          with {payload.model} on {payload.provider}, {payload.cached ? 'reused from an earlier identical request' : formatDuration(payload.latency_ms)}
        </span>
      </summary>
      <div className="space-y-2 py-2">
        {payload.purpose === 'narrate' && (
          <p className="type-small text-ink-2">This step also received the computed result as formatted text, with personal data replaced by placeholders, so it could phrase the answer.</p>
        )}
        {payload.messages.map((message, i) => (
          <div key={i}>
            <p className="mb-1 type-small font-medium text-ink-2">{ROLE[message.role] ?? message.role}</p>
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
    <div className="rounded-card bg-surface-2 p-4">
      <div className="overflow-x-auto pb-1">
        <Flow nodes={flowNodes(work)} />
      </div>

      <div className="mt-4 border-t border-line-soft pt-3">
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
              <summary className={quietLink}>Show the query that produced this answer</summary>
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
                <summary className={quietLink}>Show the second model&rsquo;s query</summary>
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
                    {i + 1}. {ATTEMPT_REASON[attempt.reason]} <span className="text-ink-2">({attempt.model})</span>
                  </p>
                  <pre className={code}>{attempt.sql}</pre>
                  {attempt.error && <p className="mt-1 text-amber-ink">This attempt failed: {attempt.error}</p>}
                </li>
              ))}
            </ol>
          </Section>
        )}

        {work.payloads.length > 0 && (
          // The verified line "No rows or personal data were sent to the AI" links straight here,
          // so this section takes focus when it does: data-section is that anchor, tabIndex lets
          // it hold focus.
          <Section title="What the model saw" data-section="payloads" tabIndex={-1}>
            <p className="mb-2 font-medium text-ink">
              Column names, types, statistics and short lists of category values (such as department names) were sent. No rows, and nothing from a personal data column.
            </p>
            <div>
              {work.payloads.map((payload, i) => (
                <Payload key={i} payload={payload} />
              ))}
            </div>
          </Section>
        )}

        {(work.cached || totalMs > 0) && (
          <p className="border-t border-line-soft pt-3 type-small text-ink-2">
            {work.cached ? 'Same question on the same data as before, so the saved answer was returned.' : `Answered in ${formatDuration(totalMs)}.`}
          </p>
        )}
      </div>
    </div>
  )
}
