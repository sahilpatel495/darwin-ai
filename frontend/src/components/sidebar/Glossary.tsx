// The Glossary tab: what "attrition" or "headcount" means for this company. Companies disagree on
// these definitions, so the analyst can edit the wording and the other names it goes by. The SQL
// pattern is shown read-only: it is what actually computes the metric, and changing it safely is
// an engineer's job, not a text box's.

import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Metric } from '../../types'
import { Button } from '../ui'
import Expander from './Expander'
import { metricProblem, parseSynonyms } from './wording'

interface GlossaryProps {
  glossary: Metric[]
  /** Files are not loaded: the definitions still read, but the server cannot be told about a change. */
  readOnly: boolean
  /** Resolves true when saved. The sidebar reports failures, so this only drives the "Saved" note. */
  onSave: (glossary: Metric[]) => Promise<boolean>
}

const FIELD = 'mt-1 block w-full rounded-control border border-rule bg-sheet px-2.5 py-1.5 type-small text-ink'
const LABEL = 'block type-small font-medium text-ink-soft'

function MetricEditor({ metric, glossary, readOnly, onSave }: GlossaryProps & { metric: Metric }) {
  const [definition, setDefinition] = useState(metric.definition)
  const [synonyms, setSynonyms] = useState(metric.synonyms.join(', '))
  const [state, setState] = useState<'idle' | 'saving' | 'saved'>('idle')

  const changed = definition.trim() !== metric.definition || parseSynonyms(synonyms).join('|') !== metric.synonyms.join('|')
  const problem = changed ? metricProblem(definition, parseSynonyms(synonyms)) : null

  const save = async (e: FormEvent) => {
    e.preventDefault()
    setState('saving')
    const edited: Metric = { ...metric, definition: definition.trim(), synonyms: parseSynonyms(synonyms) }
    const saved = await onSave(glossary.map((m) => (m.key === metric.key ? edited : m)))
    if (saved) setSynonyms(edited.synonyms.join(', ')) // show the cleaned list that was actually saved
    setState(saved ? 'saved' : 'idle')
  }

  return (
    <Expander className="border-b border-rule" label={<span className="type-body font-medium text-ink">{metric.name}</span>}>
      <form onSubmit={save} className="space-y-3 pb-4 pl-[18px]">
        <label className={LABEL}>
          Definition
          {/* Length caps keep an edited glossary from crowding out the rest of the model's instructions.
              field-sizing: the box grows to fit, so nobody scrolls a four-line box inside a scrolling sidebar. */}
          <textarea
            required
            rows={4}
            maxLength={600}
            disabled={readOnly}
            value={definition}
            onChange={(e) => {
              setDefinition(e.target.value)
              setState('idle')
            }}
            className={`${FIELD} [field-sizing:content]`}
          />
        </label>
        <label className={LABEL}>
          Other names for it, separated by commas
          <input
            type="text"
            maxLength={200}
            disabled={readOnly}
            value={synonyms}
            onChange={(e) => {
              setSynonyms(e.target.value)
              setState('idle')
            }}
            className={FIELD}
          />
        </label>
        {metric.required_roles.length > 0 && (
          <p className="type-small text-ink-soft">Needs these kinds of column: {metric.required_roles.map((role) => role.replaceAll('_', ' ')).join(', ')}.</p>
        )}
        {/* Folded by default: a SQL template with {placeholders} is for the engineer, and it sat
            between the analyst and the Save button. */}
        <details>
          <summary className="cursor-pointer type-small font-medium text-indigo">How it is calculated</summary>
          <pre className="mt-1 rounded-control bg-wash p-2 type-code break-words whitespace-pre-wrap text-ink">{metric.sql_pattern}</pre>
        </details>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" size="sm" loading={state === 'saving'} disabled={readOnly || !changed || problem !== null}>
            Save definition
          </Button>
          {/* One live region per entry, always in the DOM: a span added at save time is announced late or not at all. */}
          <span role="status" className={`min-w-0 type-small break-words ${problem ? 'text-amber' : 'text-audit'}`}>
            {problem ?? (state === 'saved' && 'Saved')}
          </span>
        </div>
      </form>
    </Expander>
  )
}

export default function Glossary({ glossary, readOnly, onSave }: GlossaryProps) {
  if (glossary.length === 0) return <p className="pt-3 type-body text-ink-soft">No metric definitions are loaded for these files.</p>
  return (
    <div>
      <p className="measure py-3 type-body text-ink-soft">
        “Attrition” can be computed three ways. These are the definitions Verity uses. Change them to match your company.
      </p>
      {glossary.map((metric) => (
        <MetricEditor key={metric.key} metric={metric} glossary={glossary} readOnly={readOnly} onSave={onSave} />
      ))}
    </div>
  )
}
