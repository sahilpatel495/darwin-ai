// One answer, in the order a person checks it: the answer in words, how far to trust it, the
// evidence (chart or table), what to keep in mind, what to ask next, and the full working.
//
// answer.text is model-phrased and the table is customer data: both are rendered as plain text
// nodes only. No markdown, no links, no HTML.
import { useState } from 'react'
import { humanize } from '../../lib/format'
import type { Answer, Confidence, Metric } from '../../types'
import ResultView from '../charts/ResultView'
import ErrorNotice from './ErrorNotice'
import HowIGotThis, { hasWork } from './HowIGotThis'

interface Props {
  answer: Answer
  glossary: Metric[]
  /** True while another question is running: chips that would start a new one are disabled. */
  busy: boolean
  onAsk: (question: string) => void
  /** Re-asks this answer's question with the chosen meaning of the ambiguous term. */
  onClarify: (term: string, value: string) => void
  onRetry: () => void
}

const LEVEL: Record<Confidence['level'], { label: string; tone: string }> = {
  high: { label: 'High confidence', tone: 'border-good/30 bg-good-soft text-good' },
  medium: { label: 'Medium confidence', tone: 'border-warn/30 bg-warn-soft text-warn' },
  low: { label: 'Low confidence', tone: 'border-bad/30 bg-bad-soft text-bad' },
}

const badge = 'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium'
const chip = 'rounded-full border border-line bg-surface px-3 py-1.5 text-left text-sm text-accent-ink hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-50'

export default function AnswerCard({ answer, glossary, busy, onAsk, onClarify, onRetry }: Props) {
  const [panel, setPanel] = useState<'confidence' | 'definition' | null>(null)
  const { work, confidence } = answer
  // undefined for a level this build does not know (a newer server): no badge rather than a crash.
  const level = confidence ? LEVEL[confidence.level] : undefined
  const flip = (name: 'confidence' | 'definition') => setPanel((open) => (open === name ? null : name))

  if (answer.kind === 'error') {
    return <ErrorNotice message={answer.text || 'This question could not be answered.'} nextStep="Ask it again, or try wording it differently." onRetry={busy ? undefined : onRetry} />
  }

  return (
    <div className="space-y-4 rounded-card border border-line bg-surface p-4 sm:p-5">
      <p className="text-base leading-relaxed whitespace-pre-wrap break-words text-ink">{answer.text}</p>

      {answer.kind === 'clarify' && answer.clarification && (
        <div>
          <p className="mb-2 text-sm text-ink-soft">{answer.clarification.question}</p>
          <div className="flex flex-wrap gap-2">
            {answer.clarification.options.map((option, i) => (
              <button key={i} type="button" disabled={busy} className={chip} onClick={() => onClarify(answer.clarification!.term, option.value)}>
                {option.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {answer.kind === 'refusal' && answer.missing && (
        <div className="rounded-lg bg-sunken px-4 py-3">
          <h4 className="text-sm font-medium text-ink">What would make this answerable</h4>
          <p className="mt-1 text-sm text-ink-soft">{answer.missing}</p>
        </div>
      )}

      {(level || work.cross_check.status === 'agreed' || work.cross_check.status === 'unavailable' || work.metrics_used.length > 0) && (
        <div>
          <div className="flex flex-wrap items-center gap-2">
            {level && (
              <button type="button" aria-expanded={panel === 'confidence'} onClick={() => flip('confidence')} className={`${badge} ${level.tone}`}>
                {level.label}
                <span aria-hidden="true">{panel === 'confidence' ? '▴' : '▾'}</span>
              </button>
            )}
            {work.cross_check.status === 'agreed' && <span className={`${badge} border-good/30 bg-good-soft text-good`}>Cross-checked by a second model</span>}
            {work.cross_check.status === 'unavailable' && <span className={`${badge} border-line bg-sunken text-ink-soft`}>Not cross-checked</span>}
            {work.metrics_used.length > 0 && (
              <button type="button" aria-expanded={panel === 'definition'} onClick={() => flip('definition')} className={`${badge} border-accent/30 bg-accent-soft text-accent-ink`}>
                Vetted definition
                <span aria-hidden="true">{panel === 'definition' ? '▴' : '▾'}</span>
              </button>
            )}
          </div>

          {panel === 'confidence' && confidence && (
            <div className="mt-2 rounded-lg bg-sunken px-4 py-3 text-sm">
              <p className="font-medium text-ink">Why this is rated {confidence.level}</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-soft">
                {confidence.reasons.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
            </div>
          )}

          {panel === 'definition' && (
            <div className="mt-2 rounded-lg bg-sunken px-4 py-3 text-sm">
              <p className="text-ink-soft">This answer uses a fixed definition from your glossary, not the model's own idea of the term.</p>
              {work.metrics_used.map((key) => {
                // The glossary is editable, so a metric may have been renamed or removed since.
                const metric = glossary.find((m) => m.key === key)
                return (
                  <p key={key} className="mt-2 text-ink-soft">
                    <span className="font-medium text-ink">{metric?.name ?? humanize(key)}</span>
                    {metric && `: ${metric.definition}`}
                  </p>
                )
              })}
            </div>
          )}
        </div>
      )}

      {work.cross_check.status === 'disagreed' && (
        <div role="note" className="rounded-lg border border-warn/30 bg-warn-soft px-4 py-3 text-sm">
          <p className="font-medium text-ink">A second model got a different result. Check this answer before you use it.</p>
          <p className="mt-1 text-ink-soft">{work.cross_check.detail}</p>
        </div>
      )}

      {answer.table && <ResultView chart={answer.chart} table={answer.table} />}

      {work.caveats.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-ink">Keep in mind</h4>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-ink-soft">
            {work.caveats.map((caveat, i) => (
              <li key={i}>{caveat}</li>
            ))}
          </ul>
        </div>
      )}

      {answer.followups.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-medium text-ink">Ask next</h4>
          <div className="flex flex-wrap gap-2">
            {answer.followups.map((followup, i) => (
              <button key={i} type="button" disabled={busy} className={chip} onClick={() => onAsk(followup)}>
                {followup}
              </button>
            ))}
          </div>
        </div>
      )}

      {hasWork(work) && <HowIGotThis work={work} />}
    </div>
  )
}
