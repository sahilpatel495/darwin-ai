// The one bold element: an answer presented as an audited statement (§6.4). Top to bottom —
// the sentence, the figure under its double rule, the ticked proof, the evidence, what to keep
// in mind, what to ask next, and the working.
//
// answer.text is model-phrased and every cell is customer data: both are rendered as plain text
// nodes only. No markdown, no links, no HTML.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Badge, Banner, Button, Chip, Figure, Popover, ProofList, Sheet, WhatsThis } from '../ui'
import { humanize } from '../../lib/format'
import { optionLabel, plainTables } from '../../lib/tables'
import { buildChartData } from '../charts/chartData'
import ResultView from '../charts/ResultView'
import type { Answer, Confidence } from '../../types'
import { useAnswerContext } from './context'
import { EXPLAIN } from '../education/explain'
import HowIGotThis, { hasWork } from './HowIGotThis'
import { proofLines } from './proof'

export interface AnswerStatementProps {
  answer: Answer
  /** `board` is the printable report: the statement, none of the controls (§6.5). */
  mode: 'thread' | 'board'
  saved?: boolean
  onToggleSaved?: () => void
  /** Asks a follow-up, re-asks with a chosen meaning, or retries this same question. */
  onAsk?: (question: string, clarification?: Record<string, string>) => void
}

const LEVELS: Confidence['level'][] = ['high', 'medium', 'low']
const linkish = 'underline decoration-rule-strong underline-offset-2 hover:decoration-current text-indigo'

/** "Try again in 12 s", counting down, enabled at zero (§6.4). The server sets the wait; we add
 *  nothing to its sentence, so the whole delay is expressed in this one label. */
function RetryButton({ seconds, disabled, onRetry }: { seconds: number | null; disabled: boolean; onRetry: () => void }) {
  const [left, setLeft] = useState(seconds ?? 0)
  useEffect(() => {
    if (left <= 0) return
    const timer = setTimeout(() => setLeft((n) => n - 1), 1000)
    return () => clearTimeout(timer)
  }, [left])
  return (
    <Button onClick={onRetry} disabled={disabled || left > 0}>
      {left > 0 ? `Try again in ${left} s` : 'Try again'}
    </Button>
  )
}

export default function AnswerStatement({ answer, mode, saved = false, onToggleSaved, onAsk }: AnswerStatementProps) {
  const { tables, glossary, newAnswerId, tourAnswerId, canAsk } = useAnswerContext()
  const [workOpen, setWorkOpen] = useState(false)
  const workPanel = useRef<HTMLDivElement>(null)
  const jumpToPayloads = useRef(false)

  const { work, confidence } = answer
  const thread = mode === 'thread'
  // Only a genuinely new answer draws its ticks and extends its rule (§4). Restored history and
  // the board are already settled, and nothing on a printed page should be mid-animation.
  const arriving = thread && newAnswerId === answer.id
  const data = useMemo(() => (answer.chart && answer.table ? buildChartData(answer.chart, answer.table) : null), [answer.chart, answer.table])
  const figure = data?.kind === 'kpi' ? data : null
  const metricName = (key: string) => glossary.find((m) => m.key === key)?.name ?? humanize(key)

  // The privacy proof line opens the working at "What the model saw" and puts focus there, so
  // the claim and its evidence are one click apart.
  const focusPayloads = () => (workPanel.current?.querySelector('[data-section="payloads"]') as HTMLElement | null)?.focus()
  useEffect(() => {
    if (!workOpen || !jumpToPayloads.current) return
    jumpToPayloads.current = false
    focusPayloads()
  }, [workOpen])
  const showWhatWasSent = () => {
    if (workOpen) return focusPayloads()
    jumpToPayloads.current = true
    setWorkOpen(true)
  }

  // An error is not a statement: no sheet, no ticks. The server's sentence, then a way to retry.
  if (answer.kind === 'error') {
    return (
      <Banner
        tone="error"
        action={thread && onAsk && <RetryButton seconds={answer.retry_after_s} disabled={!canAsk} onRetry={() => onAsk(answer.question)} />}
      >
        {answer.text || 'This question could not be answered.'}
      </Banner>
    )
  }

  const proof = proofLines(answer, metricName).map((line): ReactNode => {
    if (!thread) return line.text
    if (line.id === 'crosscheck') return <>{line.text} <WhatsThis title={EXPLAIN.crossCheck.title} body={EXPLAIN.crossCheck.body} /></>
    if (line.id === 'definition') return <>{line.text} <WhatsThis title={EXPLAIN.definition.title} body={EXPLAIN.definition.body} /></>
    if (line.id === 'privacy')
      return (
        <>
          {line.text}.{' '}
          <button type="button" onClick={showWhatWasSent} className={linkish}>
            See exactly what was sent
          </button>
        </>
      )
    return line.text
  })

  return (
    <Sheet as="article" className="px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <p className="measure min-w-0 flex-1 type-statement whitespace-pre-wrap break-words text-ink">{answer.text}</p>
        {answer.kind === 'clarify' && thread && <WhatsThis title={EXPLAIN.clarify.title} body={EXPLAIN.clarify.body} align="right" />}
        {confidence && LEVELS.includes(confidence.level) && (
          <span className="flex shrink-0 items-center gap-1.5">
            <Badge level={confidence.level} />
            {thread && confidence.reasons.length > 0 && (
              <Popover trigger="Why?" triggerLabel={`Why this answer is rated ${confidence.level}`} title={EXPLAIN.confidence.title} align="right" className={`type-small ${linkish}`}>
                <p>{EXPLAIN.confidence.body}</p>
                <ul className="mt-2 list-disc space-y-0.5 pl-4">
                  {confidence.reasons.map((reason, i) => (
                    <li key={i}>{plainTables(reason, tables)}</li>
                  ))}
                </ul>
              </Popover>
            )}
          </span>
        )}
      </div>

      {work.cached && <p className="mt-2 type-small text-ink-soft">Same question, same data: answered from memory.</p>}

      {figure && answer.chart && (
        <div className="mt-6">
          <Figure value={figure.value} caption={answer.chart.title} animate={arriving} />
          {figure.supporting.length > 0 && (
            <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-1">
              {figure.supporting.map((s) => (
                <div key={s.label} className="flex gap-2 type-small">
                  <dt className="text-ink-soft">{humanize(s.label)}</dt>
                  <dd className="m-0 text-ink tabular-nums">{s.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}

      {answer.kind === 'clarify' && answer.clarification && thread && onAsk && (
        <div className="mt-5">
          {/* The server usually sends the same sentence as the answer text; saying it twice reads as a glitch. */}
          {answer.clarification.question.toLowerCase() !== answer.text.toLowerCase() && (
            <p className="measure type-body text-ink-soft">{answer.clarification.question}</p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {answer.clarification.options.map((option, i) => (
              <Chip key={i} disabled={!canAsk} onClick={() => onAsk(answer.question, { [answer.clarification!.term]: option.value })}>
                {optionLabel(option, tables)}
              </Chip>
            ))}
          </div>
        </div>
      )}

      {answer.kind === 'refusal' && answer.missing && (
        <div className="mt-5 border-l-2 border-rule-strong pl-4">
          <h4 className="type-title text-ink">What would make this answerable</h4>
          <p className="mt-1 measure type-body text-ink-soft">{answer.missing}</p>
        </div>
      )}

      {proof.length > 0 && <ProofList className="mt-6" items={proof} animate={arriving} />}

      {work.cross_check.status === 'disagreed' && (
        // Never a tick (§6.4). The disagreement sits above the evidence, where it is read first.
        <Banner tone="error" className="mt-6" nextStep={[plainTables(work.cross_check.detail, tables), 'Check this figure before you pass it on.'].filter(Boolean).join(' ')}>
          A second AI model wrote its own query and got a different result.
        </Banner>
      )}

      {answer.table && !figure && (
        <div className="mt-6">
          <ResultView chart={answer.chart} table={answer.table} data={data} question={answer.question} board={!thread} />
        </div>
      )}

      {work.caveats.length > 0 && (
        // Marginal notes: the ledger's own way of saying "this line needs a look".
        <div className="mt-6 border-l-2 border-amber pl-4">
          <h4 className="type-title text-ink">Keep in mind</h4>
          {work.caveats.map((caveat, i) => (
            <p key={i} className="mt-1 measure type-body text-ink-soft">
              {plainTables(caveat, tables)}
            </p>
          ))}
        </div>
      )}

      {thread && onAsk && answer.followups.length > 0 && (
        <div className="mt-6">
          <h4 className="type-title text-ink">Ask next</h4>
          <div className="mt-2 flex flex-wrap gap-2">
            {answer.followups.map((followup, i) => (
              <Chip key={i} disabled={!canAsk} onClick={() => onAsk(followup)}>
                {followup}
              </Chip>
            ))}
          </div>
        </div>
      )}

      {thread && (onToggleSaved || hasWork(work)) && (
        <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-rule pt-4">
          {onToggleSaved && (
            <Button onClick={onToggleSaved} aria-pressed={saved}>
              {saved ? 'Saved' : 'Save to board'}
            </Button>
          )}
          {hasWork(work) && (
            // The tour anchors on the wrapper, not the Button: ButtonProps has no data-* index
            // signature, and a tour only needs the rectangle.
            <span data-tour={tourAnswerId === answer.id ? 'working' : undefined}>
              <Button variant="quiet" aria-expanded={workOpen} onClick={() => setWorkOpen((open) => !open)}>
                How I got this
              </Button>
            </span>
          )}
        </div>
      )}

      {thread && hasWork(work) && (
        // `hidden` rather than unmounted: the working stays in the page for find-in-page, and
        // reopening it never loses which payload the reader had already expanded.
        <div ref={workPanel} hidden={!workOpen} className="mt-4">
          <HowIGotThis work={work} tables={tables} />
        </div>
      )}
    </Sheet>
  )
}
