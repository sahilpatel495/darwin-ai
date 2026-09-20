// Ask (§8). Two screens in one component, because they are one conversation:
//
//  - empty: a greeting, the hero composer, four suggestion cards and a way to more ideas;
//  - in conversation: an 820px column of questions and answers, with the composer docked below it.
//
// A controlled component: the project record holds every completed turn, and a turn that is still
// running lives here until its answer arrives. That split is what makes the thread survive a
// reload — a half-finished question is not worth saving, and an answer always is.
//
// One question runs at a time: the backend keeps the last turns as context for follow-ups, so
// overlapping questions would make "split that by location" ambiguous.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ApiError, ask } from '../../api'
import { Banner, Button, Card, Chip, Drawer } from '../ui'
import { Glyph } from '../graphics'
import { groupSuggestions, type Suggestion } from '../../lib/suggestions'
import { columnLabel, plainAnswer } from '../../lib/tables'
import { fileNamesFrom } from '../../lib/projects'
import type { Turn } from '../../lib/projects'
import type { Catalog, StepEvent } from '../../types'
import AnswerStatement from '../answer/AnswerStatement'
import { AnswerContext } from '../answer/context'
import Composer from './Composer'
import { glyphName } from './prompts'
import Working from './Working'
import { foldStep } from './steps'

export interface ThreadProps {
  /** null = the files are no longer loaded: history is readable and asking is off (§6). */
  sessionId: string | null
  catalog: Catalog | null
  /** Controlled: the project record is the source of truth. */
  turns: Turn[]
  /** Called when a turn completes. Running turns stay local. */
  onTurnsChange: (turns: Turn[]) => void
  savedAnswerIds: string[]
  onToggleSaved: (answerId: string) => void
  onSessionExpired: () => void
  /** The analyst's name, for the greeting over an empty workspace (§8). */
  heroGreetingName?: string
  /** The four questions on the empty screen, chosen for this person's role by the shell
   *  (lib/suggestions). "More ideas" below them is every question these files can answer. */
  suggestions?: Suggestion[]
  /** Opens the Data drawer, which the top bar owns (§6). */
  onOpenData?: () => void
  /** A banner to render with the composer. §6 keeps "your files are no longer loaded" in the app
   *  shell, so this is the slot for it and the thread never invents one of its own. */
  notice?: ReactNode
  /** The `how-i-got-this` hint (§7), drawn under the first real answer — the only place the
   *  control it names exists. The shell owns which hints this reader has already dismissed, so it
   *  hands the whole thing down ready-made or hands down nothing. */
  firstAnswerTip?: ReactNode
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
  /** performance.now() when the question was sent, for the elapsed timer (§8). */
  startedAt: number
  state: 'running' | 'stopped' | 'failed'
  problem: Problem | null
}

/** How a completed turn was arrived at. Steps and chosen meanings are not worth the storage
 *  quota (§10), so they are remembered only for as long as the page is open. */
interface HowItRan {
  steps: StepEvent[]
  clarification: Record<string, string> | null
  /** How long the run took, for "Answered in 3.2 s". */
  ms: number
}

const NO_TABLES: Catalog['tables'] = [] // one empty array, so the context value stays stable
const NO_METRICS: Catalog['glossary'] = []
const NO_SUGGESTIONS: Suggestion[] = []
const NO_QUESTIONS: string[] = []

const MAX_QUESTION = 500 // AskRequest.question max_length in backend/app/contracts.py
const CARDS = 4 // §8: four suggestion cards; the rest are behind "More ideas"
const UNEXPECTED: Problem = { message: 'Something went wrong while reading the answer.', nextStep: 'Ask the question again.' }
const EXPIRED: Problem = { message: 'Your files are no longer loaded.', nextStep: 'Re-attach them to ask new questions.' }

/** The meanings already chosen that a follow-up's own wording uses. "salary" stays CTC when the
 *  follow-up says "salary"; nothing else travels, so an unrelated question starts clean. */
function carried(question: string, chosen: Record<string, string> | null): Record<string, string> | null {
  const kept = Object.entries(chosen ?? {}).filter(([term]) => question.toLowerCase().includes(term.toLowerCase()))
  return kept.length > 0 ? Object.fromEntries(kept) : null
}

function Question({ text, clarification, tables }: { text: string; clarification: Record<string, string> | null | undefined; tables: Catalog['tables'] }) {
  return (
    <div className="ml-auto w-fit max-w-[85%] rounded-xxl bg-primary-soft px-5 py-3">
      <h3 className="text-body-md whitespace-pre-wrap break-words text-ink-deep">{text}</h3>
      {/* A Set: a second clarifying question about the same word can carry the same column twice. */}
      {clarification && (
        <p className="mt-1 text-body-sm text-primary-deep">
          Using {[...new Set(Object.values(clarification))].map((ref) => columnLabel(ref, tables)).join(', ')}
        </p>
      )}
    </div>
  )
}

/** One question worth asking, as a card: press it and it is asked (§8). */
function SuggestionCard({ suggestion, accent, onAsk }: { suggestion: Suggestion; accent: string; onAsk: () => void }) {
  return (
    <Card as="button" interactive radius="xl" onClick={onAsk} className="h-full">
      <span className="flex items-center gap-2.5">
        <Glyph name={glyphName(suggestion.glyph)} size={28} accent={accent} className="text-charcoal" />
        <span className="text-body-sm text-steel">{suggestion.kind}</span>
      </span>
      <span className="mt-3 block text-body-md text-ink-deep">{suggestion.question}</span>
    </Card>
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
  heroGreetingName,
  suggestions,
  onOpenData,
  notice,
  firstAnswerTip,
}: ThreadProps) {
  const [live, setLive] = useState<LiveTurn[]>([])
  const [ran, setRan] = useState<Record<string, HowItRan>>({})
  const [newAnswerId, setNewAnswerId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [ideasOpen, setIdeasOpen] = useState(false)
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
  // Files, not tables: one workbook with two sheets is two tables and one file. Counting tables
  // made this chip say "7 files" two inches from a top bar saying 6, about the same project.
  const fileCount = catalog ? fileNamesFrom(catalog).length : 0

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

  function submitDraft() {
    if (!draft.trim() || !canAsk) return
    typedLast.current = true
    run(draft)
    setDraft('')
  }

  /** A card, a chip or the sheet: the question is asked as it is written, there and then. */
  const askNow = (question: string) => {
    typedLast.current = false
    setIdeasOpen(false)
    run(question)
  }

  /** A follow-up keeps the meanings the analyst already chose; a clarify answer adds one. */
  const askFrom = (previous: Record<string, string> | null) => (question: string, chosen?: Record<string, string>) => {
    typedLast.current = false
    run(question, chosen ? { ...previous, ...chosen } : carried(question, previous))
  }

  const context = useMemo(
    () => ({ tables, glossary: catalog?.glossary ?? NO_METRICS, newAnswerId, canAsk }),
    [tables, catalog, newAnswerId, canAsk],
  )

  const empty = turns.length === 0 && live.length === 0
  const askAgain = (turn: LiveTurn) => () => {
    typedLast.current = false
    run(turn.question, turn.clarification)
  }

  const offered = suggestions ?? NO_SUGGESTIONS
  // The sheet is everything the files can answer, under the subject it is about — not the four
  // cards again. The role is the shell's to know; here the order inside a subject is the
  // server's own, which is the order it vouched for.
  const ideas = useMemo(() => (catalog ? groupSuggestions(catalog.suggested_questions, null) : []), [catalog])
  const ideaCount = ideas.reduce((total, group) => total + group.items.length, 0)
  // Real questions, typed out one at a time while the box is empty (§8).
  const examples = (offered.length > 0 ? offered.map((suggestion) => suggestion.question) : catalog?.suggested_questions ?? NO_QUESTIONS).slice(0, 5)

  const left = MAX_QUESTION - draft.length
  const composer = (
    <Composer
      variant={empty ? 'hero' : 'docked'}
      value={draft}
      onChange={setDraft}
      onSubmit={submitDraft}
      disabled={!canAsk}
      ready={sessionId !== null}
      // The typewriter belongs to the empty screen (§8). Once there is an answer to read, a box
      // that types to itself beside it is movement with nothing to say.
      examples={empty ? examples : NO_QUESTIONS}
      idlePlaceholder={
        sessionId === null
          ? 'Re-attach your files to ask a new question'
          : running
            ? 'Working on your question'
            : empty
              ? 'Ask anything about your files'
              : 'Ask a follow-up'
      }
      fileCount={fileCount}
      onOpenData={onOpenData}
      // §8: one quiet hint, and only until the first question has been asked. The character
      // count replaces it near the limit, where it is the thing worth knowing.
      hint={left <= 50 ? `${left} characters left.` : empty || turns.length > 0 ? undefined : 'Enter to ask'}
      maxLength={MAX_QUESTION}
      textareaRef={input}
    />
  )

  return (
    <AnswerContext.Provider value={context}>
      <section aria-label="Questions and answers" className="flex h-full min-h-0 flex-col">
        {/* `relative` matters: screen-reader-only text is absolutely positioned. Without a positioned
            scroller it is laid out against the page instead, the page grows as tall as the whole
            conversation, and scrolling to a new question pushes the header off the screen. */}
        <div className="relative min-h-0 flex-1 overflow-y-auto [scrollbar-gutter:stable_both-edges]">
          <div className="mx-auto w-full max-w-[820px] px-4 py-6 sm:px-6">
            {empty ? (
              <div className="pt-6 sm:pt-12">
                {notice && <div className="mb-8">{notice}</div>}
                <h2 className="text-display-lg text-ink-deep">
                  {heroGreetingName ? `What do you want to know, ${heroGreetingName}?` : 'What do you want to know?'}
                </h2>
                <div className="mt-8">{composer}</div>

                {sessionId !== null && offered.length > 0 && (
                  <>
                    <ul className="stagger-children mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
                      {offered.slice(0, CARDS).map((suggestion, i) => (
                        <li key={suggestion.question} className="flex">
                          {/* The second accent alternates, so four cards read as a set rather than
                              as four copies of the same tile. */}
                          <SuggestionCard
                            suggestion={suggestion}
                            accent={i % 2 === 1 ? 'var(--color-purple)' : 'var(--color-primary)'}
                            onAsk={() => askNow(suggestion.question)}
                          />
                        </li>
                      ))}
                    </ul>
                    {ideaCount > offered.length && (
                      <Button variant="quiet" size="sm" className="mt-4 -ml-3.5" onClick={() => setIdeasOpen(true)}>
                        More ideas
                      </Button>
                    )}
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-8">
                {turns.map((turn, i) => {
                  const detail = ran[turn.answer.id]
                  return (
                    <article key={turn.id} ref={i === turnCount - 1 ? latestTurn : undefined} className="scroll-mt-4 space-y-4 last:min-h-[70dvh]">
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
                      {/* A clarifying question has no working to open, so the hint waits for the
                          first turn that does. */}
                      {i === 0 && turn.answer.kind === 'answer' && firstAnswerTip}
                    </article>
                  )
                })}

                {live.map((turn, i) => (
                  <article key={turn.key} ref={turns.length + i === turnCount - 1 ? latestTurn : undefined} className="scroll-mt-4 space-y-4 last:min-h-[70dvh]">
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
                      <p className="text-body-md text-slate">
                        You stopped this question.{' '}
                        <button type="button" disabled={!canAsk} className="text-primary-deep underline underline-offset-2 disabled:no-underline disabled:opacity-55" onClick={askAgain(turn)}>
                          Ask it again
                        </button>
                      </p>
                    )}
                  </article>
                ))}
              </div>
            )}
          </div>

          {/* Docked: a bar floating over the conversation, which scrolls under its blur (§8). In
              the empty state the composer is the hero above instead, so nothing is docked. */}
          {!empty && (
            <div className="sticky bottom-0 z-10 mx-auto w-full max-w-[820px] bg-linear-to-t from-canvas from-40% to-transparent px-4 pt-8 pb-4 sm:px-6 print-hide">
              {notice && <div className="mb-3">{notice}</div>}
              {composer}
            </div>
          )}
        </div>
      </section>

      {ideasOpen && (
        <Drawer open onClose={() => setIdeasOpen(false)} title="More ideas" description="Questions these files can answer. Press one to ask it.">
          <div className="space-y-6">
            {ideas.map((group) => (
              <section key={group.kind}>
                <h3 className="text-subtitle-lg text-ink-deep">{group.kind}</h3>
                <ul className="mt-3 space-y-2">
                  {group.items.map((idea) => (
                    <li key={idea.question}>
                      <Chip className="w-full" disabled={!canAsk} leading={<Glyph name={glyphName(idea.glyph)} size={18} />} onClick={() => askNow(idea.question)}>
                        {idea.question}
                      </Chip>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </Drawer>
      )}
    </AnswerContext.Provider>
  )
}
