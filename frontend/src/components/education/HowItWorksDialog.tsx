// "How Verity works", opened from the privacy shield in the header (§6.7).
//
// The one screen that answers "should I trust this with payroll data?", so it is a real sequence
// with numbered steps, followed by the two lists that matter most: what the AI is shown and what
// it is never shown. It ends by handing the reader a way to check the claim themselves, because
// a promise the product cannot be caught breaking is not worth much.

import type { ReactNode } from 'react'
import { Button, Check, Dialog } from '../ui'

interface HowItWorksDialogProps {
  open: boolean
  onClose: () => void
  /** Offered only in a workspace, where the tour has something to point at (§6.7). */
  onReplayTour?: () => void
}

/** Five steps, in the order they happen to one question. */
const STEPS: [string, string][] = [
  ['You add your files', 'Verity reads them here, in this app, and cleans them as it reads: title rows skipped, total rows dropped, ₹ amounts parsed. Every change is listed in that file’s Data Health.'],
  ['Verity describes your data to the AI', 'It sends column names, their types, how many rows there are, ranges, and short lists of repeated labels. It does not send a single row.'],
  ['You ask a question', 'The AI turns your words into one database query. It never does the arithmetic itself.'],
  ['A database computes the answer', 'The query runs over your files inside this app. Every number you see came from that run.'],
  ['The answer is checked, then worded', 'A second AI model writes its own query for the same question; when both agree, the answer says so. Wording the result is the last thing the AI does.'],
]

const SEES = [
  'Column names and what they hold, such as a ₹ amount column called Gross Pay',
  'How many rows a file has, and the earliest and latest date in it',
  'Short lists of repeated labels, such as Bengaluru or Engineering',
  'Your question, and the result of the query that answered it',
]

const NEVER = [
  'The rows of your files',
  'Names, emails and phone numbers',
  'PAN, Aadhaar, bank account numbers',
  'Anyone’s salary',
]

/** The two lists sit in inset blocks so the boundary between them is the point, not a rule. */
function Column({ title, items, marker }: { title: string; items: string[]; marker: () => ReactNode }) {
  return (
    <div className="rounded-card bg-surface-2 p-4">
      <h3 className="type-section text-ink">{title}</h3>
      <ul className="mt-2 space-y-2">
        {items.map((item) => (
          <li key={item} className="flex gap-2.5 type-small text-ink">
            {marker()}
            <span className="min-w-0">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function HowItWorksDialog({ open, onClose, onReplayTour }: HowItWorksDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="How Verity works"
      description="What happens to your files, and what the AI is allowed to see."
      size="lg"
      footer={
        <>
          {onReplayTour && (
            <Button variant="secondary" onClick={onReplayTour}>
              Show me around again
            </Button>
          )}
          <Button variant="primary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <ol className="space-y-3">
        {STEPS.map(([title, detail], i) => (
          <li key={title} className="flex gap-3">
            {/* The numeral is the sequence, so it is read out: no aria-hidden here. */}
            <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-pill bg-blue-soft type-micro font-semibold tnum text-blue-ink">
              {i + 1}
            </span>
            <span className="min-w-0">
              <span className="block type-body font-semibold text-ink">{title}</span>
              <span className="mt-0.5 block measure type-small text-ink-2">{detail}</span>
            </span>
          </li>
        ))}
      </ol>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <Column
          title="What the AI sees"
          items={SEES}
          // A neutral dot: these are facts about the data, not a promise being kept.
          marker={() => <span aria-hidden className="mt-[7px] size-1.5 shrink-0 rounded-pill bg-ink-3" />}
        />
        <Column
          title="What it never sees"
          items={NEVER}
          // A check, because this list is the promise: each line is something held back. Silent to
          // a screen reader — the heading above already says what the checks mean.
          marker={() => <Check size={16} className="mt-0.5" />}
        />
      </div>

      <p className="mt-6 measure type-body text-ink">Check it yourself: open How I got this under any answer.</p>
    </Dialog>
  )
}
