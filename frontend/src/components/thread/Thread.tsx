// The conversation (§6.3). A controlled component: the project record holds every completed
// turn, and a turn that is still running lives here until its answer arrives. That split is
// what makes the thread survive a reload — a half-finished question is not worth saving, and
// an answer always is.
//
// One question runs at a time: the backend keeps the last turns as context for follow-ups, so
// overlapping questions would make "split that by location" ambiguous.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { ApiError, ask } from '../../api'
import { Banner, Button } from '../ui'
import { columnLabel, plainAnswer } from '../../lib/tables'
import type { Turn } from '../../lib/projects'
import type { Catalog, StepEvent } from '../../types'
import AnswerStatement from '../answer/AnswerStatement'
import { AnswerContext } from '../answer/context'
import { hasWork } from '../answer/HowIGotThis'
import Working from './Working'
import { foldStep } from './steps'

export interface ThreadProps {
  /** null = the files are no longer loaded: history is readable and asking is off (§6.6). */
  sessionId: string | null
  catalog: Catalog | null
  /** Controlled: the project record is the source of truth. */
  turns: Turn[]
  /** Called when a turn completes. Running turns stay local. */
  onTurnsChange: (turns: Turn[]) => void
  savedAnswerIds: string[]
  onToggleSaved: (answerId: string) => void
  onSessionExpired: () => void
  /** The briefing, supplied by the workspace. */
  emptyState: ReactNode
  /** The re-attach banner and anything like it, rendered above the composer. */
  notice?: ReactNode
}

interface Problem {
  message: string
  nextStep: string
}

/** A question asked in this session that has not produced an answer yet. */
interface LiveTurn {
  key: number
  question: string
  /** Meanings the user picked for ambiguous terms, e.g. { salary: "salary_register.gross" }. */
  clarification: Record<string, string> | null
  steps: StepEvent[]
  /** performance.now() when the question was sent, for the elapsed timer (§11). */
  startedAt: number
  state: 'running' | 'stopped' | 'failed'
  problem: Problem | null
}

/** How a completed turn was arrived at. Steps and chosen meanings are not worth the storage
 *  quota (§7), so they are remembered only for as long as the page is open. */
interface HowItRan {
  steps: StepEvent[]
  clarification: Record<string, string> | null
  /** How long the run took, for "Answered in 3.2 s". */
  ms: number
}

const NO_TABLES: Catalog['tables'] = [] // one empty array, so the context value stays stable
const NO_METRICS: Catalog['glossary'] = []

const MAX_QUESTION = 500 // AskRequest.question max_length in backend/app/contracts.py
const UNEXPECTED: Problem = { message: 'Something went wrong while reading the answer.', nextStep: 'Ask the question again.' }
const EXPIRED: Problem = { message: 'Your files are no longer loaded.', nextStep: 'Re-attach them to ask new questions.' }

// §6.7. Three lines, only while the thread is empty, because they are about how to word a first
// question and stop being news the moment there is an answer on the screen.
const WRITING_TIPS = [
  'Name the period: “in 2025”, “in FY25”.',
  'Name the measure: “gross pay”, not “pay”.',
  'Ask a follow-up: “now split that by location”.',
]

/** The meanings already chosen that a follow-up's own wording uses. "salary" stays CTC when the
 *  follow-up says "salary"; nothing else travels, so an unrelated question starts clean. */
function carried(question: string, chosen: Record<string, string> | null): Record<string, string> | null {
  const kept = Object.entries(chosen ?? {}).filter(([term]) => question.toLowerCase().includes(term.toLowerCase()))
  return kept.length > 0 ? Object.fromEntries(kept) : null
}

function Question({ text, clarification, tables }: { text: string; clarification: Record<string, string> | null | undefined; tables: Catalog['tables'] }) {
  return (
    <div className="ml-auto w-fit max-w-[85%] rounded-hero bg-blue-soft px-4 py-2.5">
      <h3 className="type-body whitespace-pre-wrap break-words text-ink">{text}</h3>
      {/* A Set: a second clarifying question about the same word can carry the same column twice. */}
      {clarification && (
        <p className="mt-1 type-small text-blue-ink">
          Using {[...new Set(Object.values(clarification))].map((ref) => columnLabel(ref, tables)).join(', ')}
        </p>
      )}
    </div>
  )
}

export default function Thread({
  sessionId,
  catalog,
  turns,
  onTurnsChange,
  savedAnswerIds,
  onToggleSaved,
  onSessionExpired,
  emptyState,
  notice,
}: ThreadProps) {
  const [live, setLive] = useState<LiveTurn[]>([])
  const [ran, setRan] = useState<Record<string, HowItRan>>({})
  const [newAnswerId, setNewAnswerId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const nextKey = useRef(0)
  const inFlight = useRef<AbortController | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const typedLast = useRef(false)
  const latestTurn = useRef<HTMLElement>(null)
  // The completed turns as they are right now. An answer can arrive long after the question was
  // asked, and the handler must append to the list the parent holds today, not the one it held then.
  const latestTurns = useRef(turns)
  latestTurns.current = turns
  // `live` as the handlers see it, so a turn that completes can keep the steps it collected.
  const liveRef = useRef<LiveTurn[]>([])

  liveRef.current = live
  const running = live.some((turn) => turn.state === 'running')
  const canAsk = sessionId !== null && !running
  const tables = catalog?.tables ?? NO_TABLES

  // Leaving the page must not leave a query running on the server, and a different session must
  // never show the previous one's half-finished question.
  useEffect(() => () => inFlight.current?.abort(), [])
  useEffect(() => {
    inFlight.current?.abort()
    setLive([])
    setRan({})
  }, [sessionId])

  // A new question scrolls to the top of its turn; the answer then fills in below it, so the
  // reader is never pushed past the start of the answer. The newest turn reserves most of a
  // screen (last:min-h below) so there is room to scroll it to the top before the answer exists.
  // (Braces matter: newer browsers return a Promise from scrollIntoView, and an effect must not.)
  const turnCount = turns.length + live.length
  useEffect(() => {
    latestTurn.current?.scrollIntoView({ block: 'start' })
  }, [turnCount])

  // The composer is disabled while running, which drops focus. Give it back to people who typed.
  useEffect(() => {
    if (!running && typedLast.current) input.current?.focus()
  }, [running])

  // "/" jumps to the composer from anywhere, unless the keystroke is someone typing a slash.
  useEffect(() => {
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) return
      const active = document.activeElement
      if (active instanceof HTMLElement && (active.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(active.tagName))) return
      event.preventDefault()
      input.current?.focus()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  const patch = (key: number, change: (turn: LiveTurn) => LiveTurn) => setLive((all) => all.map((t) => (t.key === key ? change(t) : t)))

  function run(question: string, clarification: Record<string, string> | null = null) {
    const text = question.trim().slice(0, MAX_QUESTION)
    if (!text || !canAsk || !sessionId) return
    const key = nextKey.current++
    const startedAt = performance.now()
    const controller = new AbortController()
    inFlight.current = controller
    setLive((all) => [...all, { key, question: text, clarification, steps: [], startedAt, state: 'running', problem: null }])

    // After Stop, late steps and answers are ignored: mock mode and proxies do not honour abort.
    const alive = () => !controller.signal.aborted
    ask(sessionId, { question: text, clarification }, (step) => alive() && patch(key, (t) => ({ ...t, steps: foldStep(t.steps, step) })), controller.signal)
      .then((answer) => {
        if (!alive()) return
        // The turn moves from here to the project record in one step: it is complete, so the
        // parent owns it from now on, and the step list it was watching is kept for this page.
        setLive((all) => all.filter((t) => t.key !== key))
        setRan((all) => ({
          ...all,
          [answer.id]: { steps: liveRef.current.find((t) => t.key === key)?.steps ?? [], clarification, ms: performance.now() - startedAt },
        }))
        setNewAnswerId(answer.id)
        // Stored in the analyst's words: the board has no catalog to resolve table names with.
        onTurnsChange([...latestTurns.current, { id: answer.id, question: text, answer: plainAnswer(answer, tables), askedAt: new Date().toISOString() }])
      })
      .catch((error: unknown) => {
        if (!alive()) return
        const expired = error instanceof ApiError && error.status === 404
        const problem = expired ? EXPIRED : error instanceof ApiError ? { message: error.message, nextStep: error.nextStep } : UNEXPECTED
        patch(key, (t) => ({ ...t, state: 'failed', problem }))
        if (expired) onSessionExpired()
      })
  }

  function stop() {
    inFlight.current?.abort()
    setLive((all) => all.map((t) => (t.state === 'running' ? { ...t, state: 'stopped' } : t)))
  }

  function submit(event: { preventDefault(): void }) {
    event.preventDefault()
    if (!draft.trim() || !canAsk) return
    typedLast.current = true
    run(draft)
    setDraft('')
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // isComposing: Enter also confirms a word in Hindi and other IME keyboards; that is not a submit.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event)
  }

  /** A follow-up keeps the meanings the analyst already chose; a clarify answer adds one. */
  const askFrom = (previous: Record<string, string> | null) => (question: string, chosen?: Record<string, string>) => {
    typedLast.current = false
    run(question, chosen ? { ...previous, ...chosen } : carried(question, previous))
  }

  const context = useMemo(
    () => ({
      tables,
      glossary: catalog?.glossary ?? NO_METRICS,
      newAnswerId,
      tourAnswerId: turns.find((turn) => hasWork(turn.answer.work))?.answer.id ?? null,
      canAsk,
    }),
    [tables, catalog, newAnswerId, turns, canAsk],
  )

  const empty = turns.length === 0 && live.length === 0
  const askAgain = (turn: LiveTurn) => () => {
    typedLast.current = false
    run(turn.question, turn.clarification)
  }

  return (
    <AnswerContext.Provider value={context}>
      <section aria-label="Questions and answers" className="flex h-full min-h-0 flex-col">
        {/* `relative` matters: screen-reader-only text is absolutely positioned. Without a positioned
            scroller it is laid out against the page instead, the page grows as tall as the whole
            conversation, and scrolling to a new question pushes the header off the screen. */}
        <div className="relative min-h-0 flex-1 overflow-y-auto [scrollbar-gutter:stable_both-edges]">
          <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-6 sm:px-6">
            {empty && emptyState}

            {turns.map((turn, i) => {
              const detail = ran[turn.answer.id]
              return (
                <article key={turn.id} ref={i === turnCount - 1 ? latestTurn : undefined} className="scroll-mt-4 space-y-3 last:min-h-[70dvh]">
                  <Question text={turn.question} clarification={detail?.clarification} tables={tables} />
                  <Working steps={detail?.steps ?? []} running={false} ms={detail?.ms ?? null} />
                  <AnswerStatement
                    answer={turn.answer}
                    mode="thread"
                    saved={savedAnswerIds.includes(turn.answer.id)}
                    // Only a real answer belongs on a printed report; a clarifying question does not.
                    onToggleSaved={turn.answer.kind === 'answer' ? () => onToggleSaved(turn.answer.id) : undefined}
                    onAsk={askFrom(detail?.clarification ?? null)}
                  />
                </article>
              )
            })}

            {live.map((turn, i) => (
              <article key={turn.key} ref={turns.length + i === turnCount - 1 ? latestTurn : undefined} className="scroll-mt-4 space-y-3 last:min-h-[70dvh]">
                <Question text={turn.question} clarification={turn.clarification} tables={tables} />
                {/* No elapsed time on a stopped or failed run: it was never answered, so the
                    summary says what it got through instead of how long it took. */}
                <Working steps={turn.steps} running={turn.state === 'running'} startedAt={turn.startedAt} onStop={stop} />
                {turn.problem && (
                  <Banner tone="error" nextStep={turn.problem.nextStep} action={turn.problem !== EXPIRED && canAsk && <Button variant="primary" onClick={askAgain(turn)}>Try again</Button>}>
                    {turn.problem.message}
                  </Banner>
                )}
                {turn.state === 'stopped' && (
                  <p className="type-body text-ink-2">
                    You stopped this question.{' '}
                    <button type="button" disabled={!canAsk} className="text-blue-ink underline decoration-blue-ink/40 underline-offset-2 hover:decoration-current disabled:no-underline disabled:opacity-55" onClick={askAgain(turn)}>
                      Ask it again
                    </button>
                  </p>
                )}
              </article>
            ))}
          </div>
        </div>

        <div className="sticky bottom-0 shrink-0 bg-wash print-hide">
          {notice && <div className="mx-auto w-full max-w-3xl px-4 pt-3 sm:px-6">{notice}</div>}
          <form onSubmit={submit} data-tour="composer">
            <div className="mx-auto w-full max-w-3xl px-4 pt-3 pb-4 sm:px-6">
              {/* One white surface lifted off the wash: the place where a question is written. */}
              <div className="flex items-end gap-2 rounded-hero bg-surface p-2 shadow-2">
                <label htmlFor="verity-question" className="sr-only">
                  Your question
                </label>
                <textarea
                  id="verity-question"
                  ref={input}
                  rows={1}
                  value={draft}
                  maxLength={MAX_QUESTION}
                  disabled={running || sessionId === null}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder={
                    sessionId === null
                      ? 'Re-attach your files to ask a new question'
                      : running
                        ? 'Working on your question'
                        : 'Ask about your data, for example: average CTC by department'
                  }
                  aria-describedby="verity-question-hint"
                  // One line, growing to four, then it scrolls (§6.3).
                  // The focus ring is the shared one (§9): it draws around the writing area itself,
                  // inside the white surface, so tabbing to the composer is unmistakable.
                  className="max-h-28 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 type-body text-[16px] text-ink md:text-[15px] [field-sizing:content] placeholder:text-ink-3 disabled:text-ink-3"
                />
                <Button type="submit" variant="primary" pill disabled={!draft.trim() || !canAsk}>
                  Ask
                </Button>
              </div>
              <p id="verity-question-hint" className="mt-2 type-small text-ink-2">
                Press Enter to ask, Shift+Enter for a new line.
                {draft.length >= MAX_QUESTION - 50 && ` ${MAX_QUESTION - draft.length} characters left.`}
              </p>
              {empty && sessionId !== null && (
                <ul className="mt-1 flex flex-wrap gap-x-6 gap-y-0.5 type-small text-ink-2">
                  {WRITING_TIPS.map((tip) => (
                    <li key={tip}>{tip}</li>
                  ))}
                </ul>
              )}
            </div>
          </form>
        </div>
      </section>
    </AnswerContext.Provider>
  )
}
