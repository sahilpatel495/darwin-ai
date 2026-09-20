// Seam between the app shell (frontend-shell agent) and the conversation (frontend-thread agent).
// The shell renders <Thread> once the catalog has tables. Thread owns its own message state.
//
// One question runs at a time: the backend keeps the last turns as context for follow-ups, so
// overlapping questions would make "split that by location" ambiguous.
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { ApiError, ask } from '../../api'
import type { Answer, Catalog, StepEvent } from '../../types'
import AnswerCard from '../answer/AnswerCard'
import ErrorNotice from '../answer/ErrorNotice'
import StepList from './StepList'
import { foldStep } from './steps'

export interface ThreadProps {
  sessionId: string
  catalog: Catalog
  /** Called when the API reports the session expired (ApiError 404) so the shell can reset. */
  onSessionExpired: () => void
}

interface Problem {
  message: string
  nextStep: string
}

interface Turn {
  key: number
  question: string
  /** Meanings the user picked for ambiguous terms, e.g. { salary: "salary_register.gross" }. */
  clarification: Record<string, string> | null
  steps: StepEvent[]
  state: 'running' | 'done' | 'stopped' | 'failed'
  answer: Answer | null
  problem: Problem | null
}

const MAX_QUESTION = 500 // AskRequest.question max_length in backend/app/contracts.py
const UNEXPECTED: Problem = { message: 'Something went wrong while reading the answer.', nextStep: 'Ask the question again.' }
const EXPIRED: Problem = { message: 'Your session expired.', nextStep: 'Please upload your files again.' }

const chip = 'rounded-full border border-line bg-surface px-3 py-1.5 text-left text-sm text-accent-ink hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-50'

export default function Thread({ sessionId, catalog, onSessionExpired }: ThreadProps) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const nextKey = useRef(0)
  const inFlight = useRef<AbortController | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const typedLast = useRef(false)
  const latestTurn = useRef<HTMLElement>(null)
  const running = turns.at(-1)?.state === 'running'

  // Leaving the page must not leave a query running on the server. A new session also clears the
  // thread: answers about the previous files must never sit beside new data.
  useEffect(
    () => () => {
      inFlight.current?.abort()
      setTurns([])
    },
    [sessionId],
  )

  // A new question scrolls to the top of its turn; the answer then fills in below it, so the
  // reader is never pushed past the start of the answer. The newest turn reserves most of a
  // screen (last:min-h below) so there is room to scroll it to the top before the answer exists.
  // (Braces matter: newer browsers return a Promise from scrollIntoView, and an effect must not.)
  useEffect(() => {
    latestTurn.current?.scrollIntoView({ block: 'start' })
  }, [turns.length])

  // The composer is disabled while running, which drops focus. Give it back to people who typed.
  useEffect(() => {
    if (!running && typedLast.current) input.current?.focus()
  }, [running])

  const patch = (key: number, change: (turn: Turn) => Turn) => setTurns((all) => all.map((t) => (t.key === key ? change(t) : t)))

  function run(question: string, clarification: Record<string, string> | null = null) {
    const text = question.trim().slice(0, MAX_QUESTION)
    if (!text || running) return
    const key = nextKey.current++
    const controller = new AbortController()
    inFlight.current = controller
    setTurns((all) => [...all, { key, question: text, clarification, steps: [], state: 'running', answer: null, problem: null }])

    // After Stop, late steps and answers are ignored: mock mode and proxies do not honour abort.
    const live = () => !controller.signal.aborted
    ask(sessionId, { question: text, clarification }, (step) => live() && patch(key, (t) => ({ ...t, steps: foldStep(t.steps, step) })), controller.signal)
      .then((answer) => live() && patch(key, (t) => ({ ...t, state: 'done', answer })))
      .catch((error: unknown) => {
        if (!live()) return
        const expired = error instanceof ApiError && error.status === 404
        const problem = expired ? EXPIRED : error instanceof ApiError ? { message: error.message, nextStep: error.nextStep } : UNEXPECTED
        patch(key, (t) => ({ ...t, state: 'failed', problem }))
        if (expired) onSessionExpired()
      })
  }

  function stop() {
    inFlight.current?.abort()
    setTurns((all) => all.map((t) => (t.state === 'running' ? { ...t, state: 'stopped' } : t)))
  }

  function submit(event: { preventDefault(): void }) {
    event.preventDefault()
    if (!draft.trim() || running) return
    typedLast.current = true
    run(draft)
    setDraft('')
  }

  function askFromChip(question: string, clarification: Record<string, string> | null = null) {
    typedLast.current = false
    run(question, clarification)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // isComposing: Enter also confirms a word in Hindi and other IME keyboards; that is not a submit.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event)
  }

  return (
    <section aria-label="Questions and answers" className="flex h-full min-h-0 flex-col">
      {/* `relative` matters: screen-reader-only text is absolutely positioned. Without a positioned
          scroller it is laid out against the page instead, the page grows as tall as the whole
          conversation, and scrolling to a new question pushes the header off the screen. */}
      <div className="relative min-h-0 flex-1 overflow-y-auto [scrollbar-gutter:stable_both-edges]">
        <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-6">
          {turns.length === 0 && (
            <div>
              <h2 className="text-lg font-semibold text-ink">Ask a question about your data</h2>
              <p className="mt-1 text-sm text-ink-soft">
                Use plain English. Every number is computed by a database from your files, and each answer shows how it was worked out.
              </p>
              {catalog.suggested_questions.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {catalog.suggested_questions.map((question) => (
                    <button key={question} type="button" className={chip} onClick={() => askFromChip(question)}>
                      {question}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {turns.map((turn, i) => (
            <article key={turn.key} ref={i === turns.length - 1 ? latestTurn : undefined} className="scroll-mt-4 space-y-3 last:min-h-[70dvh]">
              <div className="ml-auto w-fit max-w-[85%] rounded-card bg-accent-soft px-4 py-2.5 text-ink">
                <h3 className="text-base font-normal whitespace-pre-wrap break-words">{turn.question}</h3>
                {turn.clarification && <p className="mt-1 text-xs text-ink-soft">Using {Object.values(turn.clarification).join(', ')}</p>}
              </div>

              <StepList steps={turn.steps} running={turn.state === 'running'} />

              {turn.answer && (
                <AnswerCard
                  answer={turn.answer}
                  glossary={catalog.glossary}
                  busy={running}
                  onAsk={(question) => askFromChip(question)}
                  onClarify={(term, value) => askFromChip(turn.question, { ...turn.clarification, [term]: value })}
                  onRetry={() => askFromChip(turn.question, turn.clarification)}
                />
              )}
              {turn.problem && <ErrorNotice message={turn.problem.message} nextStep={turn.problem.nextStep} onRetry={running || turn.problem === EXPIRED ? undefined : () => askFromChip(turn.question, turn.clarification)} />}
              {turn.state === 'stopped' && (
                <p className="text-sm text-ink-soft">
                  You stopped this question.{' '}
                  <button type="button" disabled={running} className="font-medium text-accent-ink underline disabled:opacity-50" onClick={() => askFromChip(turn.question, turn.clarification)}>
                    Ask it again
                  </button>
                </p>
              )}
            </article>
          ))}
        </div>
      </div>

      <form onSubmit={submit} className="sticky bottom-0 border-t border-line bg-surface">
        <div className="mx-auto flex w-full max-w-3xl items-end gap-2 px-4 py-3">
          <label htmlFor="verity-question" className="sr-only">
            Your question
          </label>
          <textarea
            id="verity-question"
            ref={input}
            rows={2}
            value={draft}
            maxLength={MAX_QUESTION}
            disabled={running}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={running ? 'Working on your question' : 'Ask about your data, for example: average CTC by department'}
            aria-describedby="verity-question-hint"
            className="max-h-40 min-h-[3rem] flex-1 resize-none rounded-lg border border-line bg-surface px-3 py-2 text-base text-ink [field-sizing:content] placeholder:text-ink-faint disabled:bg-sunken"
          />
          {running ? (
            <button type="button" onClick={stop} className="h-12 rounded-lg border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-sunken">
              Stop
            </button>
          ) : (
            <button type="submit" disabled={!draft.trim()} className="h-12 rounded-lg bg-accent px-5 text-sm font-medium text-white hover:bg-accent-ink disabled:cursor-not-allowed disabled:opacity-50">
              Ask
            </button>
          )}
        </div>
        <p id="verity-question-hint" className="mx-auto w-full max-w-3xl px-4 pb-2 text-xs text-ink-soft">
          Press Enter to ask, Shift+Enter for a new line.
          {draft.length >= MAX_QUESTION - 50 && ` ${MAX_QUESTION - draft.length} characters left.`}
        </p>
      </form>
    </section>
  )
}
