// The guided form for one kind of analysis (§14): a picker per input, the options, and the
// sentence that says what Run will compute.
//
// Native <select> on purpose. It is one tab stop, it groups by file with <optgroup> for free, it
// types-to-find on a desktop and it opens the platform's own wheel on a phone — a custom listbox
// would be more code and less usable. Controlled from the page so a run in the chip row can put
// the analyst's choices back exactly as they were.

import { useEffect, useRef } from 'react'
import type { AnalysisKind, ColumnChoice } from '../../types'
import { Banner, Button, Card, SegmentedControl } from '../ui'
import { groupedColumns, isComplete, noColumnsLine } from './form'

export interface AnalysisFormProps {
  kind: AnalysisKind
  columns: ColumnChoice[]
  /** Column ref to the words for it, humanised by the page. */
  labels: Record<string, string>
  inputs: Record<string, string>
  options: Record<string, string>
  onInput: (key: string, ref: string) => void
  onOption: (key: string, value: string) => void
  /** What will run, already built: the page needs the same line for the file name and the chips. */
  sentence: string
  onRun: () => void
  running: boolean
  /** The server's own sentence when it refused the combination (422), and what to do about it. */
  problem?: { message: string; nextStep: string } | null
}

const optionLabel = (choice: string): string => choice.charAt(0).toUpperCase() + choice.slice(1)

export default function AnalysisForm({
  kind,
  columns,
  labels,
  inputs,
  options,
  onInput,
  onOption,
  sentence,
  onRun,
  running,
  problem,
}: AnalysisFormProps) {
  const first = useRef<HTMLSelectElement>(null)
  const ready = isComplete(kind, inputs)

  // Choosing a kind in the gallery is a promise that the next thing to do is right here, so the
  // first picker takes the focus. preventScroll: the page does the moving, on phones only.
  useEffect(() => first.current?.focus({ preventScroll: true }), [kind.key])

  return (
    <Card as="section" aria-labelledby="analysis-form-title">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 id="analysis-form-title" className="type-card text-ink">
          {kind.name}
        </h2>
        <p className="type-small text-ink-2">{kind.description}</p>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {kind.inputs.map((input, i) => {
          const groups = groupedColumns(input, columns)
          return (
            <label key={input.key} className="block">
              <span className="type-small font-semibold text-ink">
                {input.label}
                {input.optional && <span className="font-normal text-ink-2"> (optional)</span>}
              </span>
              <select
                ref={i === 0 ? first : undefined}
                value={inputs[input.key] ?? ''}
                onChange={(event) => onInput(input.key, event.target.value)}
                className="mt-1.5 h-9 w-full rounded-input border border-line bg-surface-2 px-2 type-body text-ink"
              >
                {groups.length === 0 ? (
                  <option value="">{noColumnsLine(input)}</option>
                ) : (
                  <>
                    <option value="">{input.optional ? 'None' : 'Choose a column'}</option>
                    {groups.map((group) => (
                      <optgroup key={group.table} label={group.table}>
                        {group.columns.map((column) => (
                          <option key={column.ref} value={column.ref}>
                            {labels[column.ref] ?? column.label}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </>
                )}
              </select>
            </label>
          )
        })}
      </div>

      {kind.options.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-x-8 gap-y-4">
          {kind.options.map((option) => (
            <div key={option.key} className="min-w-0">
              <span className="type-small font-semibold text-ink">{option.label}</span>
              {/* Six ways to combine do not fit 390px: the row keeps its natural width and
                  scrolls sideways rather than squeezing "Average" into an ellipsis. */}
              <div className="mt-1.5 overflow-x-auto">
                <SegmentedControl
                  className="min-w-max"
                  size="sm"
                  label={option.label}
                  options={option.choices.map((choice) => ({ value: choice, label: optionLabel(choice) }))}
                  value={options[option.key] ?? option.choices[0] ?? ''}
                  onChange={(value) => onOption(option.key, value)}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {problem && (
        <Banner tone="error" className="mt-5" nextStep={problem.nextStep}>
          {problem.message}
        </Banner>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-card bg-surface-2 px-4 py-3">
        <p className="min-w-0 type-section text-ink">{sentence}</p>
        <Button variant="primary" onClick={onRun} loading={running} disabled={!ready}>
          Run this analysis
        </Button>
      </div>
      {!ready && <p className="mt-2 type-small text-ink-2">Choose a column in every picker above to run it.</p>}
    </Card>
  )
}
