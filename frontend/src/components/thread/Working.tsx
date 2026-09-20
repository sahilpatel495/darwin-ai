// Thinking, made visible (§8) — the first of the product's two bold moments. While a question
// runs the analyst watches each check happen, with the live detail the server sends, the time so
// far, and the model doing the writing. It is the honest answer to "is it stuck?".
//
// When the answer arrives the whole card folds into one line — "Answered in 3.2 s, 7 checks" —
// that opens again on click, because the timeline is evidence and evidence is never thrown away.
import { useEffect, useState } from 'react'
import { Button, Card, ProgressSteps, Skeleton } from '../ui'
import type { StepEvent } from '../../types'
import { modelName, summarizeRun, toProgress, waitSeconds } from './steps'

interface WorkingProps {
  steps: StepEvent[]
  running: boolean
  /** performance.now() when the question was sent, for the elapsed timer. */
  startedAt?: number
  /** How long the finished run took. Null for a turn restored from a previous visit. */
  ms?: number | null
  onStop?: () => void
}

/** The wait the models asked for, ticking down. The sentence stays the server's; only the number
 *  moves, so the analyst can see it is a wait and not a hang. */
function Countdown({ seconds }: { seconds: number }) {
  const [left, setLeft] = useState(seconds)
  useEffect(() => setLeft(seconds), [seconds])
  useEffect(() => {
    if (left <= 0) return
    const timer = setTimeout(() => setLeft((n) => n - 1), 1000)
    return () => clearTimeout(timer)
  }, [left])
  return <>All the free AI models are busy. {left > 0 ? `Trying again in ${left} s.` : 'Trying again now.'}</>
}

/** Seconds since the question was sent, to one decimal. A clock, not a spinner: it says how long
 *  this is taking, which is the thing someone waiting actually wants to know. */
function Elapsed({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(() => performance.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(performance.now()), 100)
    return () => clearInterval(timer)
  }, [])
  return <span className="tnum">{Math.max(0, (now - startedAt) / 1000).toFixed(1)} s</span>
}

/** The shape of the answer that is coming, so nothing jumps when it lands (§12). */
function AnswerSkeleton() {
  return (
    <Card aria-hidden>
      <div className="flex items-start justify-between gap-4">
        <Skeleton className="h-7 w-3/5" />
        <Skeleton className="h-7 w-36" />
      </div>
      <div className="mt-6 space-y-2.5">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
      </div>
      <Skeleton shape="card" className="mt-6 h-44 w-full" />
    </Card>
  )
}

export default function Working({ steps, running, startedAt, ms = null, onStop }: WorkingProps) {
  if (!running && steps.length === 0) return null

  const model = modelName(steps)
  // A waiting step's detail is the server's own busy sentence; only here does it start ticking.
  const progress = toProgress(steps, running).map((step) =>
    step.state === 'waiting' ? { ...step, detail: <Countdown seconds={waitSeconds(typeof step.detail === 'string' ? step.detail : '') ?? 0} /> } : step,
  )

  if (!running) {
    return (
      <details className="group">
        {/* The chevron replaces the browser's own triangle, which does not follow the type or the
            colour and sits outside the pill. */}
        <summary className="press inline-flex w-fit cursor-pointer list-none items-center gap-1.5 rounded-full border border-hairline-soft px-3.5 py-1.5 text-body-sm text-slate select-none hover:border-hairline hover:text-ink-deep [&::-webkit-details-marker]:hidden">
          <svg aria-hidden width="12" height="12" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="transition-transform duration-200 group-open:rotate-90">
            <path d="M7.5 4.5 13 10l-5.5 5.5" />
          </svg>
          {summarizeRun(steps, ms)}
        </summary>
        <Card className="mt-3">
          <ProgressSteps steps={progress} />
        </Card>
      </details>
    )
  }

  return (
    <>
      <Card>
        <div className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-2">
          <h3 className="text-heading-sm text-ink-deep">Working on it</h3>
          {model && <span className="rounded-full bg-surface-soft px-3 py-1 text-caption text-slate">{model}</span>}
          {startedAt !== undefined && (
            <span className="text-caption text-steel">
              <Elapsed startedAt={startedAt} />
            </span>
          )}
          {onStop && (
            <Button variant="ghost" size="sm" onClick={onStop} className="ml-auto">
              Stop
            </Button>
          )}
        </div>
        {/* Polite, so each check is read out as it happens without interrupting what came before. */}
        <div aria-live="polite">
          <ProgressSteps steps={progress} />
        </div>
      </Card>
      <AnswerSkeleton />
    </>
  )
}
