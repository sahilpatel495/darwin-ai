// First screen, shown until there are projects (§6.1). Its job: get a first-time analyst to a
// charted answer in under 30 seconds, which is why the sample-data button sits right under the
// drop zone instead of behind a link.
//
// The right column is a real answer card with the real demo numbers, drawn statically. The promise
// of this product is hard to describe and easy to show, so the hero shows it: this is exactly what
// the analyst gets back, down to the checked lines and the chart. It carries no controls, so there
// is nothing here to click that does not work.
//
// It is the one place on the landing page that moves: the figure counts up, the checks pop and the
// bars draw, once, on arrival — the same motion a real answer makes (§4). That moment is the
// product, so it is shown rather than described.

import { useEffect, useState } from 'react'
import { Badge, Button, Card, StatTile, VerifiedList } from '../ui'
import DropZone from './DropZone'
import UploadProgress from './UploadProgress'
import type { Busy } from './UploadProgress'

interface LandingProps {
  busy: Busy | null
  onFiles: (files: File[]) => void
  onSample: () => void
  /** Opens the dialog listing what is in the sample data (§15). Optional: Home owns that dialog. */
  onShowSample?: () => void
}

// The three lines §6.4 generates for an answer that was cross-checked and used no custom metric.
const VERIFIED = [
  'Computed by a database from your files',
  'A second AI model wrote its own query and got the same result',
  'No rows or personal data were sent to the AI',
]

// Gross pay by department, 2025, from demo_data. Widths are shares of the largest bar.
const BARS: [string, string, number][] = [
  ['Engineering', '₹20.40 Cr', 1],
  ['Sales', '₹12.05 Cr', 12.05 / 20.4],
  ['Support', '₹8.52 Cr', 8.52 / 20.4],
]

// A real sequence, so it is numbered (§6.1).
const HOW: [string, string][] = [
  ['Upload as-is', 'Drop in the exports you already have. Title rows, merged headers and ₹ symbols are sorted out while the file is read, and every change is written down.'],
  ['Ask in plain English', 'Type the question the way you would ask a colleague. When a word could mean two different columns, Verity asks which one you meant.'],
  ['Check the working', 'Open How I got this under any answer to see the question as it was read, the query that ran, and exactly what was sent to the AI.'],
]

/** The example chart: horizontal bars, because every department name is longer than ten characters (§12). */
function Bars({ drawn }: { drawn: boolean }) {
  return (
    <ul className="mt-5 space-y-2.5">
      {BARS.map(([department, amount, share]) => (
        <li key={department} className="flex items-center gap-3">
          <span className="w-24 shrink-0 truncate type-small text-ink">{department}</span>
          <span aria-hidden className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-pill bg-fill">
            <span
              className="block h-full rounded-pill bg-series-1 transition-[width] duration-[400ms] ease-[var(--ease-enter)]"
              style={{ width: `${(drawn ? share : 0) * 100}%` }}
            />
          </span>
          <span className="w-[4.5rem] shrink-0 text-right type-small font-semibold tnum text-ink">{amount}</span>
        </li>
      ))}
    </ul>
  )
}

export default function Landing({ busy, onFiles, onSample, onShowSample }: LandingProps) {
  // One frame with the bars at zero, then they grow. `useEffect` and not a CSS animation because
  // the same flag switches the count-up and the checks on, so the card arrives as one moment.
  const [drawn, setDrawn] = useState(false)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setDrawn(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  // Source order is headline, upload, example, how it works: on a phone the drop zone stays above
  // the fold and the example is the reward for scrolling.
  return (
    <div className="mx-auto grid w-full max-w-6xl gap-x-12 gap-y-10 px-4 py-10 sm:px-6 sm:py-14 lg:grid-cols-[1fr_26rem]">
      <div>
        <h1 className="type-page text-ink sm:text-[40px] sm:leading-[46px] sm:tracking-[-0.02em]">
          Ask your spreadsheets.
          <br />
          Verify every answer.
        </h1>
        <p className="mt-5 measure type-body text-ink-2">
          Upload the HR exports you already have, messy headings and all. Ask a question in plain English.
        </p>
        <p className="mt-2 measure type-body text-ink-2">
          A database computes every number from your files, and every answer opens to show exactly how it was worked out.
        </p>

        <div className="mt-8 max-w-md">
          {busy ? (
            <Card>
              <UploadProgress busy={busy} />
            </Card>
          ) : (
            <DropZone onFiles={onFiles} />
          )}
          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
            <Button variant="primary" onClick={onSample} disabled={busy !== null}>
              Try with sample HR data
            </Button>
            {onShowSample && (
              <Button variant="ghost" onClick={onShowSample}>
                See what’s inside
              </Button>
            )}
            <p className="type-small text-ink-2">A made-up company of 500 employees.</p>
          </div>
        </div>
      </div>

      <div>
        <Card as="section" hero aria-label="Example answer">
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
            <p className="min-w-0 type-card text-ink">Engineering had the highest gross pay in 2025</p>
            <Badge level="high" />
          </div>
          <StatTile value="₹20.40 Cr" label="Gross pay, 2025" animate={drawn} className="mt-4" />
          <VerifiedList items={VERIFIED} animate={drawn} className="mt-5" />
          <Bars drawn={drawn} />
        </Card>
        {/* Said plainly, so nobody reads the demo numbers as their own. */}
        <p className="mt-3 type-small text-ink-2">An example answer. Yours look like this, computed from your own files.</p>
      </div>

      <section className="lg:col-span-2">
        <h2 className="type-section text-ink">How it works</h2>
        <ol className="mt-3 grid gap-3 sm:grid-cols-3">
          {HOW.map(([title, detail], i) => (
            <Card as="li" key={title}>
              <span className="inline-flex size-7 items-center justify-center rounded-pill bg-blue-soft type-small font-semibold tnum text-blue-ink">
                {i + 1}
              </span>
              <h3 className="mt-3 type-body font-semibold text-ink">{title}</h3>
              <p className="mt-1 type-small text-ink-2">{detail}</p>
            </Card>
          ))}
        </ol>
      </section>
    </div>
  )
}
