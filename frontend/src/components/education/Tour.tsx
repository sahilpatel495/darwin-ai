// The first-run tour (§6.7): four steps, once, only in a workspace.
//
// It points at things that are already on the screen instead of covering them, so the analyst can
// read the real interface while the tour talks about it. There is no backdrop and nothing is made
// inert: a tour that holds the page hostage is a tour people learn to dismiss without reading.
// An anchor another owner has not placed yet — the first "How I got this" before any answer
// exists — is simply skipped, and if none of the four are on screen the tour finishes silently.

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { Button } from '../ui'
// `tourSteps`, not `tour`: on a case-insensitive filesystem `./tour` and this file are the same
// path, so the import would resolve to the steps module and the component would never load.
import { placePanel, TOUR_STEPS } from './tourSteps'
import type { Box, TourAnchor, TourStep } from './tourSteps'

const find = (anchor: TourAnchor) => document.querySelector<HTMLElement>(`[data-tour="${anchor}"]`)

/** Only used for the first frame, which is corrected before paint by the layout effect below. */
const START = { top: 0, left: 0 }

export interface TourProps {
  /** True the first time an analyst reaches a workspace. Setting it to false closes the tour. */
  run: boolean
  /** Called once, when the tour is finished or skipped. The project record remembers it. */
  onDone: () => void
}

export default function Tour({ run, onDone }: TourProps) {
  const [steps, setSteps] = useState<TourStep[]>([])
  const [index, setIndex] = useState(0)
  const [ring, setRing] = useState<Box | null>(null)
  const [pos, setPos] = useState(START)
  const panel = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const bodyId = useId()

  // The latest onDone, so the effect that starts the tour depends only on `run`. Were onDone in
  // its dependencies, a caller passing an inline arrow would restart the tour on every render.
  const done = useRef(onDone)
  useEffect(() => {
    done.current = onDone
  })

  useEffect(() => {
    if (!run) return setSteps([])
    const present = TOUR_STEPS.filter((step) => find(step.anchor))
    setSteps(present)
    setIndex(0)
    if (present.length === 0) done.current()
  }, [run])

  const step = steps[index]
  const last = index === steps.length - 1

  const finish = useCallback(() => {
    setSteps([])
    done.current()
  }, [])

  /** Measure the anchor and the panel, then decide where the panel goes. */
  const update = useCallback(() => {
    if (!step) return
    const anchor = find(step.anchor)
    // The anchor can vanish mid-tour (a drawer closes, an answer is cleared). Move on rather
    // than point at nothing.
    if (!anchor) return setIndex((i) => (i + 1 < steps.length ? i + 1 : i))
    const rect = anchor.getBoundingClientRect()
    const box = { top: rect.top, left: rect.left, width: rect.width, height: rect.height }
    const size = panel.current?.getBoundingClientRect()
    setRing(box)
    setPos(placePanel(box, { width: size?.width ?? 320, height: size?.height ?? 200 }, { width: innerWidth, height: innerHeight }))
  }, [step, steps.length])

  // Before paint, so the panel is never seen in the wrong place. `nearest` and no `behavior`
  // keep the scroll instant, which is what a reduced-motion reader asked for anyway.
  useLayoutEffect(() => {
    if (!step) return
    find(step.anchor)?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    update()
  }, [step, update])

  // Focus moves to the panel, which is how a screen reader announces each step.
  useEffect(() => {
    if (step) panel.current?.focus()
  }, [step])

  useEffect(() => {
    if (!step) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') finish()
    }
    // Capture: the anchor may sit inside its own scroller, whose scroll event does not bubble.
    addEventListener('scroll', update, true)
    addEventListener('resize', update)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      removeEventListener('scroll', update, true)
      removeEventListener('resize', update)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [step, update, finish])

  if (!step) return null

  return (
    <>
      {ring && (
        <div
          aria-hidden
          className="pointer-events-none fixed z-40 rounded-control bg-indigo/10"
          // The ring is drawn outside the box so it never covers the thing it points at.
          style={{ top: ring.top - 4, left: ring.left - 4, width: ring.width + 8, height: ring.height + 8, boxShadow: '0 0 0 2px var(--color-indigo)' }}
        />
      )}
      <div
        ref={panel}
        role="dialog"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        tabIndex={-1}
        style={pos}
        className="fixed z-50 w-80 max-w-[calc(100vw-1rem)] animate-fade rounded-control border border-rule bg-sheet p-4 shadow-float"
      >
        <p className="type-small text-ink-soft">
          Step {index + 1} of {steps.length}
        </p>
        <h2 id={titleId} className="mt-1 type-title text-ink">
          {step.title}
        </h2>
        <p id={bodyId} className="mt-1 type-small text-ink-soft">
          {step.body}
        </p>
        <div className="mt-4 flex items-center gap-2">
          <Button size="sm" variant="quiet" onClick={finish}>
            Skip
          </Button>
          <span className="ml-auto flex gap-2">
            {index > 0 && (
              <Button size="sm" onClick={() => setIndex((i) => i - 1)}>
                Back
              </Button>
            )}
            <Button size="sm" variant="primary" onClick={() => (last ? finish() : setIndex((i) => i + 1))}>
              {last ? 'Done' : 'Next'}
            </Button>
          </span>
        </div>
      </div>
    </>
  )
}
