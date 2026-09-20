// First screen, shown until the session has tables (§6.1). Its job: get a first-time analyst to a
// charted answer in under 30 seconds, which is why the sample-data button sits right under the
// drop zone instead of behind a link.
//
// The right column is a real answer statement with the real demo numbers, drawn statically. The
// promise of this product is hard to describe and easy to show, so the hero shows it: this is
// exactly what the analyst gets back, down to the double rule and the ticked proof. It does not
// animate — nothing on a landing page should perform — and it carries no controls, so there is
// nothing here to click that does not work.

import { Button, Figure, ProofList, RuledRow, Sheet } from '../ui'
import DropZone from './DropZone'
import UploadProgress from './UploadProgress'
import type { Busy } from './UploadProgress'

interface LandingProps {
  busy: Busy | null
  onFiles: (files: File[]) => void
  onSample: () => void
}

// The three lines §6.4 generates for an answer that was cross-checked and used no custom metric.
const PROOF = [
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

export default function Landing({ busy, onFiles, onSample }: LandingProps) {
  // Source order is headline, upload, example, how it works: on a phone the drop zone stays above
  // the fold and the example is the reward for scrolling.
  return (
    <div className="mx-auto grid w-full max-w-5xl gap-x-12 gap-y-12 px-4 py-10 sm:px-6 sm:py-14 lg:grid-cols-[1fr_25rem]">
      <div>
        <h1 className="type-headline text-ink">
          Ask your spreadsheets.
          <br />
          Verify every answer.
        </h1>
        <p className="mt-5 measure type-body text-ink-soft">
          Upload the HR exports you already have, messy headings and all. Ask a question in plain English.
        </p>
        <p className="mt-2 measure type-body text-ink-soft">
          A database computes every number from your files, and every answer opens to show exactly how it was worked out.
        </p>

        <div className="mt-8 max-w-md">
          {busy ? <UploadProgress busy={busy} /> : <DropZone onFiles={onFiles} />}
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
            <Button onClick={onSample} disabled={busy !== null}>
              Try with sample HR data
            </Button>
            <p className="type-small text-ink-soft">A made-up company of 500 employees.</p>
          </div>
        </div>
      </div>

      <div>
        <Sheet as="section" aria-label="Example answer" className="p-5">
          <p className="type-statement text-ink">Engineering had the highest gross pay in 2025</p>
          <Figure value="₹20.40 Cr" caption="Gross pay, 2025" className="mt-4" />
          <ProofList items={PROOF} className="mt-5" />
          <ul className="mt-5">
            {BARS.map(([department, amount, share]) => (
              <RuledRow as="li" key={department} className="items-center">
                <span className="w-24 shrink-0 type-small text-ink">{department}</span>
                <span aria-hidden className="h-2 min-w-0 flex-1 bg-wash">
                  <span className="block h-2 bg-indigo" style={{ width: `${share * 100}%` }} />
                </span>
                <span className="w-20 shrink-0 text-right type-small text-ink tabular-nums">{amount}</span>
              </RuledRow>
            ))}
          </ul>
        </Sheet>
        {/* Said plainly, so nobody reads the demo numbers as their own. */}
        <p className="mt-2 type-small text-ink-soft">An example answer. Yours look like this, computed from your own files.</p>
      </div>

      <section className="lg:col-span-2">
        <h2 className="type-title text-ink">How it works</h2>
        <ol className="mt-3 grid gap-x-10 border-t border-rule sm:grid-cols-3">
          {HOW.map(([title, detail], i) => (
            <RuledRow as="li" key={title}>
              <span className="w-5 shrink-0 font-serif text-[20px] leading-7 font-medium text-ink-soft tabular-nums">{i + 1}</span>
              <span className="min-w-0">
                <span className="block type-title text-ink">{title}</span>
                <span className="mt-0.5 block type-small text-ink-soft">{detail}</span>
              </span>
            </RuledRow>
          ))}
        </ol>
      </section>
    </div>
  )
}
