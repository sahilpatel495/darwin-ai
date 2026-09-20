// The sentence builder (§8): "Show me the average of [Annual CTC ▾] by [Department ▾]".
//
// The gaps are native <select>s wearing a pill. Native on purpose: one tab stop each, <optgroup>
// groups them by file for free, type-to-find on a desktop, the platform's own wheel on a phone —
// a custom listbox would be more code and less usable. Controlled from the page, so a chip in the
// row of runs can put the analyst's choices back exactly as they were.

import { useEffect, useRef } from 'react'
import type { ReactNode, Ref } from 'react'
import type { AnalysisInput, AnalysisKind, AnalysisOption, ColumnChoice } from '../../types'
import { Banner, Button, Card, PillTabs, cx } from '../ui'
import {
  groupValues,
  groupedColumns,
  isComplete,
  MISSING,
  noColumnsLine,
  sentenceParts,
  shortLabel,
  slotForMessage,
  unmentionedInputs,
} from './form'
import type { SentenceSlot } from './form'

export interface SentenceBuilderProps {
  kind: AnalysisKind
  columns: ColumnChoice[]
  /** Column ref to the words for it, humanised by the page. */
  labels: Record<string, string>
  inputs: Record<string, string>
  options: Record<string, string>
  onInput: (key: string, ref: string) => void
  onOption: (key: string, value: string) => void
  onRun: () => void
  running: boolean
  /** The server's own sentence when it refused the combination (422), and what to do about it. */
  problem?: { message: string; nextStep: string } | null
  /** True once the analyst has picked a kind themselves: only then does a gap take the focus. */
  autoFocus?: boolean
}

// "Lowest" and "Highest" rather than "Min" and "Max": the sentence reads that way too.
const CHOICE_WORDS: Record<string, string> = { min: 'Lowest', max: 'Highest' }
const choiceLabel = (choice: string): string => CHOICE_WORDS[choice] ?? choice.charAt(0).toUpperCase() + choice.slice(1)

/** One gap: a pill that opens the platform's own list. */
function Slot({
  label,
  value,
  placeholder,
  keepEmpty = false,
  invalid = false,
  onChange,
  inputRef,
  children,
}: {
  label: string
  value: string
  /** What the gap says before anything is chosen. */
  placeholder: string
  /** The empty choice stays on the list: this gap may be left out on purpose. */
  keepEmpty?: boolean
  invalid?: boolean
  onChange: (value: string) => void
  inputRef?: Ref<HTMLSelectElement>
  children: ReactNode
}) {
  const chosen = Boolean(value)
  return (
    <span className="relative inline-flex max-w-full">
      <select
        ref={inputRef}
        aria-label={label}
        aria-invalid={invalid || undefined}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        // Tailwind's reset gives a form control `font: inherit`, so a gap in a 28px sentence is
        // 28px without being told; only the colour and the weight are set here.
        className={cx(
          'press inline-flex max-w-full appearance-none items-center truncate rounded-full border py-1 pr-9 pl-4',
          chosen
            ? 'border-transparent bg-primary-soft font-medium text-primary-deep'
            : 'border-dashed border-hairline bg-canvas text-steel hover:border-charcoal hover:text-ink',
          invalid && 'border-solid border-critical text-critical',
        )}
      >
        {(keepEmpty || !chosen) && <option value="">{placeholder}</option>}
        {children}
      </select>
      <svg aria-hidden viewBox="0 0 20 20" fill="none" className="pointer-events-none absolute top-1/2 right-3.5 size-4 -translate-y-1/2">
        <path d="m5.5 8 4.5 4.5L14.5 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  )
}

export default function SentenceBuilder({
  kind,
  columns,
  labels,
  inputs,
  options,
  onInput,
  onOption,
  onRun,
  running,
  problem,
  autoFocus = false,
}: SentenceBuilderProps) {
  const first = useRef<HTMLSelectElement>(null)
  const ready = isComplete(kind, inputs, options)
  const parts = sentenceParts(kind, options)
  const extras = unmentionedInputs(kind, options)
  const values = groupValues(kind, inputs, columns)
  // Which picker the server's refusal is about, so its sentence can sit beside that picker and
  // the picker itself can be marked, rather than a banner at the bottom of the card.
  const blamed = problem ? slotForMessage(problem.message, kind) : null
  const blame = (of: 'input' | 'option', key: string) =>
    problem && blamed?.of === of && blamed.key === key ? <Refusal problem={problem} /> : null

  // Choosing a kind in the gallery is a promise that the next thing to do is right here, so the
  // first gap takes the focus — but only for a kind the analyst chose, never on page load.
  useEffect(() => {
    if (autoFocus) first.current?.focus({ preventScroll: true })
  }, [kind.key, autoFocus])

  /** The options for one column picker, grouped by the file they came from. */
  const columnOptions = (input: AnalysisInput) =>
    groupedColumns(input, columns).map((group) => (
      <optgroup key={group.table} label={group.table}>
        {group.columns.map((column) => (
          <option key={column.ref} value={column.ref}>
            {labels[column.ref] ?? column.label}
          </option>
        ))}
      </optgroup>
    ))

  const empty = (input: AnalysisInput) => groupedColumns(input, columns).length === 0

  let gaps = 0
  const gap = (slot: SentenceSlot) => {
    if (slot.of === 'values') {
      const option = kind.options.find((item) => item.key === slot.key)
      if (!option) return null
      return (
        <Slot
          key={slot.key}
          label={shortLabel(option.label)}
          value={options[slot.key] ?? ''}
          placeholder={values.length === 0 ? 'a value' : MISSING}
          invalid={blamed?.of === 'option' && blamed.key === slot.key}
          onChange={(value) => onOption(slot.key, value)}
        >
          {values.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Slot>
      )
    }
    const input = kind.inputs.find((item) => item.key === slot.key)
    if (!input) return null
    const isFirst = gaps++ === 0
    // An optional gap nobody has filled is an offer, not a hole in the grammar: it stands on its
    // own wearing its own label ("Separate lines for"), and the words that join it to the
    // sentence — ", with a line for each" — arrive with the column that makes them true.
    const offered = Boolean(input.optional) && !inputs[slot.key]
    return (
      <span key={slot.key}>
        {slot.lead && <span>{offered ? ' ' : slot.lead}</span>}
        <Slot
          label={input.label}
          value={inputs[slot.key] ?? ''}
          placeholder={empty(input) ? noColumnsLine(input) : input.optional ? input.label : MISSING}
          keepEmpty={input.optional}
          invalid={blamed?.of === 'input' && blamed.key === slot.key}
          onChange={(value) => onInput(slot.key, value)}
          inputRef={isFirst ? first : undefined}
        >
          {columnOptions(input)}
        </Slot>
      </span>
    )
  }

  const inSentence = blamed?.of === 'input' && !extras.some((input) => input.key === blamed.key)
  const rows = kind.options.filter((option) => option.choices.length > 0)

  return (
    <Card as="section" radius="xxxl" aria-label={kind.name}>
      {/* The sentence is the control and the promise at once: what it reads is what will run.
          Laid out as running text, not as a row of boxes: the words carry their own spaces, so
          ", this month against the one before" keeps its comma against the pill before it. The
          line height is what stops two lines of pills from touching when the sentence wraps. */}
      <p className="text-heading-md leading-[1.7] text-ink-deep">
        Show me{' '}
        {parts.map((part, i) =>
          typeof part === 'string' ? <span key={`text-${i}`}>{i === 0 ? lowerFirst(part) : part}</span> : gap(part),
        )}
      </p>
      {inSentence && problem && <Refusal problem={problem} />}

      {(extras.length > 0 || rows.length > 0) && (
        <div className="mt-8 space-y-5 border-t border-hairline-soft pt-6">
          {extras.map((input) => (
            <div key={input.key}>
              <Row label={input.label}>
                <Slot
                  label={input.label}
                  value={inputs[input.key] ?? ''}
                  placeholder={empty(input) ? noColumnsLine(input) : input.optional ? 'None' : 'Choose a column'}
                  keepEmpty={input.optional}
                  invalid={blamed?.of === 'input' && blamed.key === input.key}
                  onChange={(value) => onInput(input.key, value)}
                >
                  {columnOptions(input)}
                </Slot>
              </Row>
              {blame('input', input.key)}
            </div>
          ))}

          {rows.map((option) => (
            <div key={option.key}>
              <Row label={shortLabel(option.label)}>
                <Choices option={option} value={options[option.key] || option.choices[0]} onChange={(value) => onOption(option.key, value)} />
              </Row>
              {blame('option', option.key)}
            </div>
          ))}
        </div>
      )}

      {/* A refusal that names no picker still belongs to what was just pressed. */}
      {!blamed && problem && <Refusal problem={problem} />}

      <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-hairline-soft pt-6">
        {/* Only while a gap is still open. When the sentence is complete it is already written out
            in full, in 24px type, three inches above this line — and the line used to promise an
            exact name ("Called Gross by Department…") that the server then title-cases into
            something slightly different. A restatement that is also not quite true. */}
        <p className="min-w-0 text-body-sm text-steel">{ready ? '' : 'Fill every gap in the sentence to run it.'}</p>
        <Button variant="action" onClick={onRun} loading={running} disabled={!ready}>
          Run
        </Button>
      </div>
    </Card>
  )
}

/** "Average CTC" starts the title; inside "Show me …" it is one sentence, so it starts small. */
const lowerFirst = (line: string): string => line.charAt(0).toLowerCase() + line.slice(1)

/** A named row under the sentence: what the sentence says in words rather than in a gap. */
function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <span className="text-body-sm font-bold text-ink-deep">{label}</span>
      {children}
    </div>
  )
}

function Choices({ option, value, onChange }: { option: AnalysisOption; value: string; onChange: (value: string) => void }) {
  return (
    // Six ways to combine do not fit 390px: PillTabs keeps its natural width and scrolls sideways
    // rather than squeezing "Average" into an ellipsis. `min-w-0 flex-1` is what lets it: inside
    // the flex row above, a child will not shrink below its content without it, so the pills took
    // 568px and the whole phone page scrolled sideways instead of the pills.
    <PillTabs
      className="min-w-0 flex-1"
      size="sm"
      label={shortLabel(option.label)}
      active={value}
      onChange={onChange}
      tabs={option.choices.map((choice) => ({ id: choice, label: choiceLabel(choice) }))}
    />
  )
}

const Refusal = ({ problem }: { problem: { message: string; nextStep: string } }) => (
  <Banner tone="error" className="mt-5" nextStep={problem.nextStep}>
    {problem.message}
  </Banner>
)
