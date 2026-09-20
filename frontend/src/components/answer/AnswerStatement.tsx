// The answer card (§8) — the second of the product's two bold moments. Top to bottom: the
// sentence and how confident it is, the figure, what was verified, what the database noticed,
// the chart, what to keep in mind, what to ask next, and a compact toolbar over the working.
//
// answer.text is model-phrased and every cell is customer data: both are rendered as plain text
// nodes only. No markdown, no links, no HTML.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Badge, Banner, Button, Card, Chip, Dialog, IconButton, Popover, SavedIcon, StatTile, VerifiedList, WhatsThis, toast } from '../ui'
import { csvFileName, downloadCsv, toCsv } from '../../lib/csv'
import { humanize } from '../../lib/format'
import { optionLabel, plainTables } from '../../lib/tables'
import { buildChartData } from '../charts/chartData'
import { CopyIcon, DownloadIcon, ExpandIcon } from '../charts/icons'
import ResultView from '../charts/ResultView'
import type { Answer, ChartSpec, Confidence } from '../../types'
import { useAnswerContext } from './context'
import { EXPLAIN } from '../education/explain'
import HowIGotThis, { hasWork } from './HowIGotThis'
import { proofLines } from './proof'

export interface AnswerStatementProps {
  answer: Answer
  /** `board` is the printable report: the statement, none of the controls (§8). */
  mode: 'thread' | 'board'
  saved?: boolean
  onToggleSaved?: () => void
  /** Asks a follow-up, re-asks with a chosen meaning, or retries this same question. */
  onAsk?: (question: string, clarification?: Record<string, string>) => void
}

const LEVELS: Confidence['level'][] = ['high', 'medium', 'low']
const linkish = 'text-primary-deep underline underline-offset-2 hover:decoration-2'

/** "Try again in 12 s", counting down, enabled at zero (§8). The server sets the wait; we add
 *  nothing to its sentence, so the whole delay is expressed in this one label. */
function RetryButton({ seconds, disabled, onRetry }: { seconds: number | null; disabled: boolean; onRetry: () => void }) {
  const [left, setLeft] = useState(seconds ?? 0)
  useEffect(() => {
    if (left <= 0) return
    const timer = setTimeout(() => setLeft((n) => n - 1), 1000)
    return () => clearTimeout(timer)
  }, [left])
  return (
    <Button variant="primary" onClick={onRetry} disabled={disabled || left > 0}>
      {left > 0 ? `Try again in ${left} s` : 'Try again'}
    </Button>
  )
}

export default function AnswerStatement({ answer, mode, saved = false, onToggleSaved, onAsk }: AnswerStatementProps) {
  const { tables, glossary, newAnswerId, canAsk } = useAnswerContext()
  const [workOpen, setWorkOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  // The shape the reader switched to, remembered by the card rather than by the view: "Open the
  // chart larger" mounts a second view, and it has to open on what they were looking at.
  const [chartType, setChartType] = useState<ChartSpec['type'] | null>(null)
  const workPanel = useRef<HTMLDivElement>(null)
  const jumpToPayloads = useRef(false)

  const { work, confidence } = answer
  const thread = mode === 'thread'
  // Only a genuinely new answer counts up and pops its checks (§4). Restored history and the
  // board are already settled, and nothing on a printed page should be mid-animation.
  const arriving = thread && newAnswerId === answer.id
  const data = useMemo(() => (answer.chart && answer.table ? buildChartData(answer.chart, answer.table) : null), [answer.chart, answer.table])
  const figure = data?.kind === 'kpi' ? data : null
  const metricName = (key: string) => glossary.find((m) => m.key === key)?.name ?? humanize(key)
  // One value is the hero figure, drawn above; anything else is a result to draw here.
  const shown = answer.table && !figure ? answer.table : null
  // A spreadsheet of one number, or of no rows at all, helps nobody: those have no toolbar.
  const result = shown && shown.rows.length > 0 ? shown : null
  const caption = answer.chart?.title || 'Result'

  // The privacy line opens the working at "What the model saw" and puts focus there, so the claim
  // and its evidence are one click apart.
  const focusPayloads = () => (workPanel.current?.querySelector('[data-section="payloads"]') as HTMLElement | null)?.focus()
  useEffect(() => {
    if (!workOpen || !jumpToPayloads.current) return
    jumpToPayloads.current = false
    focusPayloads()
  }, [workOpen])
  /**
   * Opening the working is the product's signature moment, and it unfolds below the fold, behind
   * the docked composer. Bringing its first line into view is the difference between "nothing
   * happened" and "here is the working".
   */
  const openWork = (open: boolean) => {
    setWorkOpen(open)
    if (!open) return
    const still = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
    requestAnimationFrame(() => workPanel.current?.scrollIntoView({ block: 'nearest', behavior: still ? 'auto' : 'smooth' }))
  }

  const showWhatWasSent = () => {
    if (workOpen) return focusPayloads()
    jumpToPayloads.current = true
    setWorkOpen(true)
  }

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(answer.text)
      toast('Answer copied')
    } catch {
      // Clipboard is blocked on plain http and inside some embedded views.
      toast('Could not copy. Select the sentence instead.', 'error')
    }
  }

  // An error is not a statement: no card, no checks. The server's sentence, then a way to retry.
  if (answer.kind === 'error') {
    return (
      <Banner tone="error" action={thread && onAsk && <RetryButton seconds={answer.retry_after_s} disabled={!canAsk} onRetry={() => onAsk(answer.question)} />}>
        {answer.text || 'This question could not be answered.'}
      </Banner>
    )
  }

  const verified = proofLines(answer, metricName).map((line): ReactNode => {
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
    <Card as="article">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        {/* `basis-64` rather than `min-w-0`: with a minimum of zero the headline shrinks to a
            column narrower than one word and "employees" breaks in half on a phone. Given a base
            width it is the confidence badge that wraps to its own line, which is what should
            happen — the sentence is the answer. */}
        <h3 className="measure flex-1 basis-64 text-heading-sm whitespace-pre-wrap break-words text-ink-deep">{answer.text}</h3>
        {answer.kind === 'clarify' && thread && <WhatsThis title={EXPLAIN.clarify.title} body={EXPLAIN.clarify.body} align="right" />}
        {confidence && LEVELS.includes(confidence.level) && (
          <span className="flex shrink-0 items-center gap-2">
            <Badge level={confidence.level} />
            {thread && confidence.reasons.length > 0 && (
              <Popover trigger="Why?" triggerLabel={`Why this answer is rated ${confidence.level}`} title={EXPLAIN.confidence.title} align="right" className={`text-body-sm ${linkish}`}>
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

      {work.cached && <p className="mt-3 text-body-sm text-steel">Same question, same data: answered from memory.</p>}

      {figure && answer.chart && (
        <div className="mt-6 rounded-xl bg-surface-soft px-6 py-5">
          <StatTile value={figure.value} label={answer.chart.title} animate={arriving} />
          {figure.supporting.length > 0 && (
            <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-1">
              {figure.supporting.map((s) => (
                <div key={s.label} className="flex gap-2 text-body-sm">
                  <dt className="text-slate">{humanize(s.label)}</dt>
                  <dd className="m-0 tnum text-ink">{s.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}

      {answer.kind === 'clarify' && answer.clarification && thread && onAsk && (
        <div className="mt-6">
          {/* The server usually sends the same sentence as the answer text; saying it twice reads as a glitch. */}
          {answer.clarification.question.toLowerCase() !== answer.text.toLowerCase() && (
            <p className="measure text-body-md text-slate">{answer.clarification.question}</p>
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
        <div className="mt-6 rounded-xl bg-surface-soft px-5 py-4">
          <h4 className="text-body-sm font-bold text-ink-deep">What would make this answerable</h4>
          <p className="mt-1 measure text-body-md text-slate">{answer.missing}</p>
        </div>
      )}

      {verified.length > 0 && <VerifiedList className="mt-6" items={verified} animate={arriving} />}

      {/* Computed by the server from the result itself, never phrased by a model (§8). */}
      {answer.insights.length > 0 && (
        <ul className="mt-5 flex flex-wrap gap-2">
          {answer.insights.map((insight, i) => (
            <li key={i}>
              <Chip static>{insight}</Chip>
            </li>
          ))}
        </ul>
      )}

      {work.cross_check.status === 'disagreed' && (
        // Never a check (§8). The disagreement sits above the chart, where it is read first.
        <Banner tone="error" className="mt-6" nextStep={[plainTables(work.cross_check.detail, tables), 'Check this figure before you pass it on.'].filter(Boolean).join(' ')}>
          A second AI model wrote its own query and got a different result.
        </Banner>
      )}

      {shown && (
        <div className="mt-6">
          <ResultView chart={answer.chart} table={shown} data={data} allowSwitch={thread} type={chartType ?? undefined} onTypeChange={setChartType} />
        </div>
      )}

      {work.caveats.length > 0 && (
        <Banner
          tone="warn"
          className="mt-6"
          nextStep={work.caveats.map((caveat, i) => (
            <span key={i} className="mt-0.5 block">
              {plainTables(caveat, tables)}
            </span>
          ))}
        >
          Keep in mind
        </Banner>
      )}

      {thread && onAsk && answer.followups.length > 0 && (
        <div className="mt-6">
          <h4 className="text-body-sm font-bold text-charcoal">Ask next</h4>
          <div className="mt-2 flex flex-wrap gap-2">
            {answer.followups.map((followup, i) => (
              <Chip key={i} disabled={!canAsk} onClick={() => onAsk(followup)}>
                {followup}
              </Chip>
            ))}
          </div>
        </div>
      )}

      {thread && (onToggleSaved || result || hasWork(work)) && (
        <div className="mt-6 flex flex-wrap items-center gap-1.5 border-t border-hairline-soft pt-4">
          {onToggleSaved && (
            <IconButton
              label={saved ? 'Saved to board' : 'Save to board'}
              variant={saved ? 'soft' : 'ghost'}
              size="sm"
              aria-pressed={saved}
              onClick={() => {
                onToggleSaved()
                if (!saved) toast('Saved to board')
              }}
            >
              <SavedIcon size={18} />
            </IconButton>
          )}
          <IconButton label="Copy answer" variant="ghost" size="sm" onClick={copyAnswer}>
            <CopyIcon size={18} />
          </IconButton>
          {result && (
            <>
              {/* The file holds the raw values (full precision, ISO dates) of every row the answer
                  has, not only the rows drawn. */}
              <IconButton
                label="Download CSV"
                variant="ghost"
                size="sm"
                onClick={() => downloadCsv(csvFileName(answer.question || caption), toCsv(result.columns, result.rows))}
              >
                <DownloadIcon size={18} />
              </IconButton>
              <IconButton label="Open the chart larger" variant="ghost" size="sm" onClick={() => setExpanded(true)}>
                <ExpandIcon size={18} />
              </IconButton>
            </>
          )}
          {hasWork(work) && (
            // The one control here that keeps its words: it is the invitation to check the number,
            // and an icon would make the product's whole argument hover-only.
            <Button variant="quiet" size="sm" className="ml-auto" aria-expanded={workOpen} onClick={() => openWork(!workOpen)}>
              How I got this
            </Button>
          )}
        </div>
      )}

      {thread && hasWork(work) && (
        // `hidden` rather than unmounted: the working stays in the page for find-in-page, and
        // reopening it never loses which payload the reader had already expanded.
        <div ref={workPanel} hidden={!workOpen} className="mt-5">
          <HowIGotThis work={work} tables={tables} />
        </div>
      )}

      {/* Mounted only while it is open: otherwise every answer on the page would carry a second
          copy of its chart and table in the DOM, for a dialog nobody has asked for. */}
      {expanded && result && (
        <Dialog open onClose={() => setExpanded(false)} title={caption} size="xl">
          {/* The dialog is wider than the card; without a floor it would be exactly as short, and
              "open the chart larger" would only ever mean "wider". */}
          <ResultView chart={answer.chart} table={result} allowSwitch type={chartType ?? undefined} onTypeChange={setChartType} minHeight={480} />
        </Dialog>
      )}
    </Card>
  )
}
