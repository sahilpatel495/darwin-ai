// "See the working" (§7): the dark card that answers the only question a sceptical reader has —
// where does the number actually come from?
//
// It is a sequence, so it is drawn as one: a rail down the left that fills, and six stops that
// light in turn as it passes them. Two of the six say "AI", and that is the whole argument of the
// card: the model writes and words, the database computes, and the check sits between them.
//
// The reveal runs once, when the card comes into view, and never again — a loop here would fight
// the hero's AppPreview for attention, and this card is read, not watched. Under reduced motion
// every stop is simply already lit.

import { cx } from '../ui'
import { FLOW } from './copy'
import { useSequence } from './reveal'

export default function Showcase() {
  const [card, lit] = useSequence(FLOW.length)

  return (
    <div
      ref={card}
      // `items-center`: the six stops make this card tall, and a heading pinned to the top of a
      // 26rem column leaves two thirds of the left side empty at 1280.
      className="rounded-xxxl bg-ink-deep px-6 py-10 text-white sm:px-10 sm:py-14 lg:grid lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:items-center lg:gap-16"
    >
      <div>
        <h2 className="text-display-lg">See the working</h2>
        <p className="mt-4 measure text-subtitle-md text-white/75">
          One question, from the words you typed to the figure you can quote. Every answer in the product opens to show
          this same trail for itself.
        </p>
      </div>

      <ol className="relative mt-10 lg:mt-0">
        {/* The rail: a faint track with a cobalt fill that grows as the stops light. */}
        <span aria-hidden className="absolute top-2 bottom-2 left-[11px] w-0.5 rounded-full bg-white/15">
          <span
            className="block w-full rounded-full bg-primary transition-[height] duration-[var(--dur-draw)] ease-[var(--ease-out)]"
            style={{ height: `${(Math.max(0, lit - 1) / (FLOW.length - 1)) * 100}%` }}
          />
        </span>

        {FLOW.map((step, i) => {
          const on = i < lit
          return (
            <li key={step.label} className="relative flex gap-5 pb-8 last:pb-0">
              <span
                aria-hidden
                className={cx(
                  'mt-1.5 size-6 shrink-0 rounded-full border-2 transition-colors duration-[var(--dur-surface)] ease-[var(--ease-out)]',
                  on ? 'border-primary bg-primary' : 'border-white/25 bg-ink-deep',
                )}
              />
              {/* A stop that has not been reached is invisible, not dimmed: dimmed white text on
                  ink falls under 4.5:1, and there is nothing worth reading at half contrast. */}
              <div className={cx('min-w-0 transition-opacity duration-[var(--dur-surface)]', on ? 'opacity-100' : 'opacity-0')}>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <h3 className="text-subtitle-lg">{step.label}</h3>
                  {step.ai && (
                    <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-caption font-bold text-white">AI</span>
                  )}
                </div>
                <p className="mt-1 measure text-body-md text-white/75">{step.detail}</p>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
