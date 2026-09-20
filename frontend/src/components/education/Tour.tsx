// The first-run tour (§6.7): six steps, once, only in a workspace.
//
// It points at things that are already on the screen instead of covering them, so the analyst can
// read the real interface while the tour talks about it. There is no backdrop and nothing is made
// inert: a tour that holds the page hostage is a tour people learn to dismiss without reading.
// An anchor that is not there — the first "How I got this" before any answer exists — is simply
// skipped, and if none of the six are on screen the tour finishes silently.

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { Button, cx } from '../ui'
// `tourSteps`, not `tour`: on a case-insensitive filesystem `./tour` and this file are the same
// path, so the import would resolve to the steps module and the component would never load.
import { anchorSelectors, placePanel, TOUR_STEPS } from './tourSteps'
import type { Box, TourStep } from './tourSteps'

/** The first selector that finds something: the placed anchor wins over the nav rail fallback. */
function find(step: TourStep): HTMLElement | null {
  for (const selector of anchorSelectors(step)) {
    const found = document.querySelector<HTMLElement>(selector)
    if (found) return found
  }
  return null
}

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
    const present = TOUR_STEPS.filter((step) => find(step))
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
    const anchor = find(step)
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
    find(step)?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
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
          className="pointer-events-none fixed z-40 rounded-card bg-blue/8 transition-all duration-200 ease-[var(--ease-standard)]"
          // The ring is drawn outside the box so it never covers the thing it points at.
          style={{ top: ring.top - 4, left: ring.left - 4, width: ring.width + 8, height: ring.height + 8, boxShadow: '0 0 0 2px var(--color-blue)' }}
        />
      )}
      <div
        ref={panel}
        role="dialog"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        tabIndex={-1}
        style={pos}
        className="dialog-in fixed z-50 w-80 max-w-[calc(100vw-1rem)] rounded-card bg-surface p-4 shadow-3"
      >
        <p className="sr-only">
          Step {index + 1} of {steps.length}
        </p>
        {/* The dots are the progress: six short lines, the one you are on twice as long. */}
        <div aria-hidden className="flex gap-1">
          {steps.map((other, i) => (
            <span
              key={other.anchor}
              className={cx('h-1 rounded-pill transition-all duration-200 ease-[var(--ease-standard)]', i === index ? 'w-5 bg-blue' : 'w-2 bg-fill')}
            />
          ))}
        </div>
        <h2 id={titleId} className="mt-3 type-section text-ink">
          {step.title}
        </h2>
        <p id={bodyId} className="mt-1 type-small text-ink-2">
          {step.body}
        </p>
        <div className="mt-4 flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={finish}>
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
