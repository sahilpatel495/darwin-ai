// `#/how` (§6, §7). The page that answers "should I put payroll data into this?".
//
// The centre of it is a diagram rather than a promise: one file, its columns down the left, and
// beside each one the exact sentence the AI is given about it. Half of them say "never sent".
// The mapping is drawn from `backend/app/catalog/prompt_context.py`, which is the only code in the
// product allowed to turn data into prompt text — so what this page claims is what that file does,
// and the claim is checkable.
//
// It takes no props: it is reachable signed in or out, and it must read the same either way.

import { HOME, TRUST } from '../lib/route'
import { useSequence } from '../components/marketing/reveal'
import { Glyph } from '../components/graphics'
import type { GlyphName } from '../components/graphics/Glyph'
import { Badge, Card, Check, cx } from '../components/ui'

/** The five things that happen to one question, in order. */
const STEPS: [string, string][] = [
  [
    'Your files are read here',
    'Title rows above the header are skipped, a total row at the bottom is dropped, ₹ symbols come out of the numbers and dates are read in one consistent format. Every change is listed, file by file, in Data.',
  ],
  [
    'Your columns are described to the AI',
    'Column names and types, how many rows a file has, ranges, and the repeated labels in short list columns — because a model needs the real spelling of “Bengaluru” to filter on it. Not one row goes with them.',
  ],
  ['You ask a question', 'The model turns your words into one database query. It is never asked to do the arithmetic, and it never sees a figure to do it with.'],
  ['A database computes the answer', 'The query runs over your own files, inside this app. Every number you read came out of that run and nowhere else.'],
  [
    'A second model checks it, then it is worded',
    'A different model writes its own query for the same question without seeing the first. When the two agree the answer says so; when they disagree it says that too, and drops its rating.',
  ],
]

interface ColumnFact {
  /** What the column is called in the file, and an example of what is in it. */
  column: string
  example: string
  /** The sentence the AI is given, or null when the column is held back entirely. */
  told: string | null
}

/** One file, column by column. The four `null`s are the argument of the page. */
const COLUMNS: ColumnFact[] = [
  { column: 'Employee ID', example: '000142', told: 'A code, one per row. The codes themselves are never listed.' },
  { column: 'Full name', example: 'Priya Sharma', told: null },
  { column: 'Work email', example: 'priya.s@example.com', told: null },
  { column: 'PAN', example: 'ABCPS1234F', told: null },
  { column: 'Bank account', example: '50100234567890', told: null },
  { column: 'Department', example: 'Engineering', told: 'Text, with all six of its repeated labels spelled out, so a filter can match them exactly.' },
  { column: 'Joining date', example: '21/06/2022', told: 'A date, with the earliest and latest date in the column.' },
  { column: 'Gross pay', example: '₹18,40,000', told: 'A ₹ amount, with the smallest and largest figure in the column. No row’s figure goes with it.' },
]

const CHECKS: [GlyphName, string, string][] = [
  ['receipt', 'Open the working on any answer', '“How I got this” shows the question as it was read, the query that ran, and the exact words the AI was sent. Not a summary of them — the words.'],
  ['table', 'Open Data on any file', 'Every change made while the file was read, counted line by line, and the list of columns being held back from the AI.'],
  ['shield', 'Read the trust report', 'A fixed set of test questions with correct answers worked out separately, scored, with every failure listed rather than hidden.'],
]

export default function HowItWorks() {
  const [diagram, lit] = useSequence(COLUMNS.length, 260)

  return (
    <div className="mx-auto w-full max-w-[1120px] px-4 py-12 sm:px-6 sm:py-16">
      <h1 className="measure text-display-lg text-ink-deep">How DarwinLens works</h1>
      <p className="mt-5 measure text-subtitle-md text-slate">
        An AI writes the query and words the result. A database does the arithmetic, over your own files, here. Those
        are two different jobs, and keeping them apart is the whole design.
      </p>

      {/* --- The sequence ------------------------------------------------------------------- */}
      <ol className="mt-14 space-y-8 sm:space-y-10">
        {STEPS.map(([title, detail], i) => (
          <li key={title} className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-[3rem_minmax(0,1fr)]">
            <span className="inline-flex size-9 items-center justify-center rounded-full bg-ink-deep text-button-md text-white tnum">
              {i + 1}
            </span>
            <div>
              <h2 className="text-heading-sm text-ink-deep">{title}</h2>
              <p className="mt-2 measure text-body-md text-slate">{detail}</p>
            </div>
          </li>
        ))}
      </ol>

      {/* --- The diagram -------------------------------------------------------------------- */}
      <section className="mt-20">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h2 className="text-heading-lg text-ink-deep">What the AI sees, column by column</h2>
          <Badge tone="success">4 of 8 held back</Badge>
        </div>
        <p className="mt-3 measure text-body-md text-slate">
          One file on the left, exactly as you exported it. On the right, everything the AI is told about it.
        </p>

        <Card radius="xxl" className="mt-8" flush>
          {/* A header row that only exists on a wide screen: at 390 each pair is read as a block,
              and two column titles floating above a stack would describe nothing. */}
          <div className="hidden grid-cols-2 gap-8 border-b border-hairline-soft px-8 py-4 sm:grid">
            <h3 className="text-body-sm font-bold text-ink-deep">In your file, on this server</h3>
            <h3 className="text-body-sm font-bold text-ink-deep">Given to the AI</h3>
          </div>

          <div ref={diagram}>
            {COLUMNS.map((fact, i) => (
              <div
                key={fact.column}
                className={cx(
                  'grid grid-cols-1 gap-x-8 gap-y-2 border-b border-hairline-soft px-6 py-4 last:border-0 sm:grid-cols-2 sm:px-8',
                  'transition-opacity duration-[var(--dur-surface)] ease-[var(--ease-out)]',
                  i < lit ? 'opacity-100' : 'opacity-0',
                )}
              >
                <div className="min-w-0">
                  <p className="text-body-md font-medium text-ink-deep">{fact.column}</p>
                  <p className="mt-0.5 text-body-sm text-steel">{fact.example}</p>
                </div>
                {/* The check marks the promise being kept, so it belongs on the held-back lines.
                    What is sent gets a neutral dot: it is a fact about the data, not a virtue. */}
                {fact.told ? (
                  <p className="flex min-w-0 gap-3 text-body-md text-ink">
                    <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-stone" />
                    <span className="min-w-0">{fact.told}</span>
                  </p>
                ) : (
                  <p className="flex min-w-0 items-center gap-2.5">
                    <Check size={18} />
                    <span className="text-body-md font-bold text-success">Never sent</span>
                  </p>
                )}
              </div>
            ))}
          </div>
        </Card>

        <p className="mt-4 measure text-body-sm text-steel">
          One function in the product is allowed to turn your data into words for a model. Holding it to one place is
          what makes this testable rather than a promise, and the test runs on every change.
        </p>
      </section>

      {/* --- Check it yourself --------------------------------------------------------------- */}
      <section className="mt-20">
        <h2 className="text-heading-lg text-ink-deep">Check it yourself</h2>
        <p className="mt-3 measure text-body-md text-slate">
          A claim you cannot catch being broken is not worth much. Three places to catch this one.
        </p>
        <ul className="stagger-children mt-8 grid grid-cols-1 gap-4 md:grid-cols-3">
          {CHECKS.map(([glyph, title, detail], i) => (
            <Card as="li" key={title} radius="xxl">
              <Glyph
                name={glyph}
                size={40}
                accent={i === 1 ? 'var(--color-purple)' : undefined}
                className="text-charcoal"
              />
              <h3 className="mt-5 text-heading-sm text-ink-deep">{title}</h3>
              <p className="mt-2 text-body-md text-slate">{detail}</p>
            </Card>
          ))}
        </ul>
      </section>

      <Card radius="xxxl" tone="soft" className="mt-16 flex flex-wrap items-center justify-between gap-6">
        <div>
          <h2 className="text-heading-sm text-ink-deep">See it on a real company</h2>
          <p className="mt-2 measure text-body-md text-slate">
            The sample company loads in a couple of seconds and answers questions straight away.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <a
            href={HOME}
            className="press inline-flex h-11 items-center rounded-full bg-ink-deep px-[30px] text-button-md text-white no-underline hover:bg-ink"
          >
            Open DarwinLens
          </a>
          <a
            href={TRUST}
            className="press inline-flex h-11 items-center rounded-full border-2 border-ink-deep px-7 text-button-md text-ink-deep no-underline hover:bg-canvas"
          >
            Read the trust report
          </a>
        </div>
      </Card>
    </div>
  )
}
