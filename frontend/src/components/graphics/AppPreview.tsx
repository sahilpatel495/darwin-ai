// The landing hero's "photograph" (§4): a miniature of a real answer card that plays the whole
// product in eight seconds — a question types itself, three checks tick, the figure counts up to
// ₹54.67 Cr, three bars grow — and then starts again.
//
// It is a picture of the product, not the product: nothing here calls the API, and the figures are
// the ones the sample company actually returns, so the loop never promises something a visitor
// cannot reproduce by pressing "Try the live demo".
//
// One clock. An interval ticks `elapsed` and every frame of the animation is derived from it, so
// there is no chain of timeouts to cancel, nothing drifts out of step, and the whole thing stops
// dead by not starting the interval. It stops when the hero scrolls away (an idle tab should not
// be animating) and when the reader has asked for reduced motion, in which case the final frame is
// what they see — the same information, standing still.

import { useEffect, useRef, useState } from 'react'
import { cx } from '../ui/cx'

const QUESTION = 'What did we spend on salaries last year?'

/** Milestones on the one clock, in milliseconds. */
const T = {
  typeFrom: 300,
  typeTo: 2600,
  steps: [2800, 3300, 3800],
  figureFrom: 4100,
  figureTo: 4800,
  barsFrom: 4500,
  barsTo: 5300,
  // The answer is the point of the loop, so it holds for about seven seconds of the eleven and a
  // half. At 8.6s the card sat empty for nearly half of every cycle, which on a landing hero reads
  // as a product still loading rather than one that has already answered.
  loop: 11600,
} as const

const STEPS = ['Read your files', 'Checked the query', 'Second model agreed'] as const

// The sample company's own 2025 gross pay, by department: Engineering ₹20.40 Cr, Sales ₹12.05 Cr
// and Support ₹8.52 Cr of a ₹54.67 Cr total across the 467 people who were paid. Copied from what
// the live demo actually answers, so the hero is a photograph of the product rather than a
// mock-up of it — press "Try the live demo", ask this question, and these are the figures back.
const BARS = [
  { label: 'Engineering', share: 1, value: '₹20.40 Cr' },
  { label: 'Sales', share: 0.59, value: '₹12.05 Cr' },
  { label: 'Support', share: 0.42, value: '₹8.52 Cr' },
] as const

const TOTAL = 54.67
const clamp01 = (n: number) => Math.min(1, Math.max(0, n))
/** Ease-out: fast at the start, so a figure is readable long before it settles. */
const ease = (t: number) => 1 - (1 - t) ** 3
const between = (elapsed: number, from: number, to: number) => ease(clamp01((elapsed - from) / (to - from)))

export interface AppPreviewProps {
  className?: string
}

export default function AppPreview({ className }: AppPreviewProps) {
  const frame = useRef<HTMLDivElement>(null)
  const [elapsed, setElapsed] = useState<number>(T.loop) // the settled frame, until the clock says otherwise
  const [playing, setPlaying] = useState(false)
  // Followed rather than sampled once: a reader can turn reduced motion on while the page is
  // open, and on a hash-routed app the page they turn it on is the page they stay on.
  const [reduced, setReduced] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches)

  useEffect(() => {
    const query = matchMedia('(prefers-reduced-motion: reduce)')
    const follow = () => setReduced(query.matches)
    follow()
    query.addEventListener('change', follow)
    return () => query.removeEventListener('change', follow)
  }, [])

  // Play only while on screen. A hero that has scrolled past is still a composited layer being
  // repainted sixteen times a second otherwise.
  useEffect(() => {
    const node = frame.current
    if (!node) return
    const observer = new IntersectionObserver(([entry]) => setPlaying(entry.isIntersecting), { threshold: 0.25 })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    // Off-screen or reduced motion: park on the last frame, which is the whole answer, standing
    // still. Parking rather than freezing wherever the clock stopped matters — a half-typed
    // question and a ₹0.00 figure would read as a product that had failed.
    if (!playing || reduced) {
      setElapsed(T.loop)
      return
    }
    setElapsed(0)
    const started = performance.now()
    const id = setInterval(() => setElapsed((performance.now() - started) % T.loop), 60)
    return () => clearInterval(id)
  }, [playing, reduced])

  const typed = QUESTION.slice(0, Math.round(between(elapsed, T.typeFrom, T.typeTo) * QUESTION.length))
  const asking = elapsed < T.typeTo
  const figure = TOTAL * between(elapsed, T.figureFrom, T.figureTo)
  const bars = between(elapsed, T.barsFrom, T.barsTo)
  const answered = elapsed >= T.figureFrom

  return (
    <div
      ref={frame}
      // Decorative: the sentences it animates are all repeated in the copy around the hero, and a
      // screen reader has no use for a nine-second loop.
      aria-hidden
      className={cx('w-full max-w-[520px] rounded-xxxl border border-hairline-soft bg-canvas p-4 sm:p-6', className)}
    >
      {/* The question, typing itself into the composer. */}
      <div className="flex min-w-0 items-center gap-3 rounded-full border border-hairline bg-surface-soft px-4 py-3">
        <span className="min-w-0 flex-1 truncate text-body-sm text-ink">
          {typed || <span className="text-steel">Ask anything about your files…</span>}
          {asking && <span className="caret ml-px inline-block w-px align-middle text-primary">▍</span>}
        </span>
        <span className="inline-flex shrink-0 items-center rounded-full bg-primary px-3 py-1 text-caption font-bold text-white">Ask</span>
      </div>

      {/* The working: three checks, ticking in turn. */}
      <ul className="mt-4 space-y-2">
        {STEPS.map((step, i) => {
          const done = elapsed >= T.steps[i]
          return (
            <li key={step} className="flex items-center gap-2.5">
              <span
                className={cx(
                  'inline-flex size-[18px] shrink-0 items-center justify-center rounded-full transition-colors duration-200',
                  done ? 'bg-success text-white' : 'border-2 border-hairline',
                )}
              >
                {done && (
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" className="check-pop">
                    <path d="m3.5 8.5 3 3 6-6.5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </span>
              <span className={cx('text-body-sm transition-colors duration-200', done ? 'text-ink' : 'text-stone')}>{step}</span>
            </li>
          )
        })}
      </ul>

      {/* The answer. It fades in as one block so the card never jumps: the space is held from the
          first frame by the min-height below. */}
      <div
        className="mt-5 min-h-[188px] border-t border-hairline-soft pt-5 transition-opacity duration-300"
        style={{ opacity: answered ? 1 : 0 }}
      >
        <span className="inline-flex items-center gap-1.5 rounded-full bg-success-soft px-2.5 py-1 text-caption font-bold text-success">
          <span className="size-1.5 rounded-full bg-success" />
          High confidence
        </span>
        <p className="mt-3 text-heading-lg text-ink-deep tnum">₹{figure.toFixed(2)} Cr</p>
        <p className="mt-1 text-body-sm text-slate">Total gross pay across 467 people, 2025</p>

        <div className="mt-4 space-y-2.5">
          {BARS.map((bar) => (
            <div key={bar.label} className="flex items-center gap-3">
              <span className="w-[88px] shrink-0 truncate text-caption text-steel">{bar.label}</span>
              <span className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-surface-soft">
                <span
                  className="block h-full rounded-full bg-primary"
                  style={{ width: `${bars * bar.share * 100}%`, transition: 'none' }}
                />
              </span>
              <span className="w-[74px] shrink-0 text-right text-caption text-ink tnum">{bar.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
