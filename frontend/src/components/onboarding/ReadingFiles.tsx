// Onboarding step three (§7): the animated sequence that *is* the education.
//
// Nothing here is a loading state — the files were already read before this screen appeared. It is
// a replay, at a speed a person can follow, of what happened to their own files, ending with the
// three questions those files can answer. Somebody who watches this has learned that DarwinLens
// cleans as it reads, that it finds links, and that personal data is held back from the AI,
// without being told any of it.
//
// One clock for the ticks. Under reduced motion every stage is already done and the ready card is
// on screen: the information is the point, the pacing is the flourish.

import { useEffect, useRef, useState } from 'react'
import type { Catalog } from '../../types'
import { Glyph } from '../graphics'
import { Button, Card, ProgressRing, ProgressSteps, useCountUp } from '../ui'
import type { ProgressStep } from '../ui'
import { firstQuestions, readingStages } from './reading'

/** Slow enough to read one line, fast enough that five of them are not a wait. */
const TICK_MS = 900

/** The detail line, with its first count rolling up as the stage lands (§4). */
function Detail({ text, animate }: { text: string; animate: boolean }) {
  return <>{useCountUp(text, animate)}</>
}

export interface ReadingFilesProps {
  catalog: Catalog
  /** A question card asks it straight away — no second screen, no "start asking" button. */
  onAsk: (question: string) => void
  onOverview: () => void
  /** Called once, when the sequence finishes. The caller records that onboarding is done. */
  onReady?: () => void
}

export default function ReadingFiles({ catalog, onAsk, onOverview, onReady }: ReadingFilesProps) {
  const stages = readingStages(catalog)
  const questions = firstQuestions(catalog)
  const [done, setDone] = useState(0)

  useEffect(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return setDone(stages.length)
    const timer = setInterval(() => {
      setDone((n) => {
        if (n >= stages.length) {
          clearInterval(timer)
          return n
        }
        return n + 1
      })
    }, TICK_MS)
    return () => clearInterval(timer)
  }, [stages.length])

  const finished = done >= stages.length

  // Held in a ref so the effect below depends on `finished` alone: with `onReady` in the
  // dependencies, a caller passing an inline arrow would fire it again on every render.
  const ready = useRef(onReady)
  useEffect(() => {
    ready.current = onReady
  })
  // Reported after the render that finishes it, not inside the tick, so the caller's own state
  // change cannot land in the middle of this component updating.
  useEffect(() => {
    if (finished) ready.current?.()
  }, [finished])

  const steps: ProgressStep[] = stages.map((stage, i) => ({
    id: stage.id,
    label: stage.label,
    state: i < done ? 'done' : i === done ? 'active' : 'pending',
    // A count before the stage has run would be a promise, not a report.
    detail: i <= done - 1 ? <Detail text={stage.detail} animate={i === done - 1} /> : undefined,
  }))

  return (
    <div>
      <div className="flex items-center gap-5">
        <ProgressRing value={done / stages.length} size={72} label="Reading your files">
          {done}/{stages.length}
        </ProgressRing>
        <div className="min-w-0">
          <h1 className="text-heading-lg text-ink-deep">{finished ? 'Your workspace is ready' : 'Reading your files'}</h1>
          <p className="mt-1 text-body-md text-slate">
            {finished
              ? 'All of it is in Data, whenever you want to check a line of it again.'
              : 'This all happened to your files a moment ago. Here is what it found.'}
          </p>
        </div>
      </div>

      <ProgressSteps steps={steps} className="mt-8" />

      {finished && (
        <div className="rise-in mt-10 border-t border-hairline-soft pt-10">
          <h2 className="text-heading-sm text-ink-deep">Three questions your files can answer</h2>
          <ul className="stagger-children mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
            {questions.map((question, i) => (
              <li key={question} className="flex">
                <Card
                  as="button"
                  radius="xl"
                  interactive
                  onClick={() => onAsk(question)}
                  className="flex h-full flex-col items-start gap-4"
                >
                  <Glyph
                    name={(['bars', 'trend', 'donut'] as const)[i % 3]}
                    size={32}
                    accent={i === 1 ? 'var(--color-purple)' : undefined}
                    className="text-charcoal"
                  />
                  <span className="text-body-md text-ink-deep">{question}</span>
                </Card>
              </li>
            ))}
          </ul>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button variant="primary" onClick={onOverview}>
              See the overview
            </Button>
            <p className="text-body-sm text-steel">Figures your files already answer, with no question to write.</p>
          </div>
        </div>
      )}
    </div>
  )
}
