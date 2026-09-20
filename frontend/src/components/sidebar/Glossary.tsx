// The Glossary tab: what "attrition" or "headcount" means for this company. Companies disagree on
// these definitions, so the analyst can edit the wording and the other names it goes by. The SQL
// pattern is shown read-only: it is what actually computes the metric, and changing it safely is
// an engineer's job, not a text box's.

import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Metric } from '../../types'
import { Button, Input, Textarea, cx } from '../ui'
import Expander from './Expander'
import { metricProblem, parseSynonyms } from './wording'

interface GlossaryProps {
  glossary: Metric[]
  /** Files are not loaded: the definitions still read, but the server cannot be told about a change. */
  readOnly: boolean
  /** Resolves true when saved. The drawer reports failures, so this only drives the "Saved" note. */
  onSave: (glossary: Metric[]) => Promise<boolean>
}

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
    <Expander
      chevronAtEnd
      className="border-b border-hairline-soft last:border-b-0"
      summaryClassName="px-3 py-4"
      label={
        <>
          <span className="block text-subtitle-lg text-ink-deep">{metric.name}</span>
          <span className="mt-0.5 block truncate text-body-sm text-slate">{metric.definition}</span>
        </>
      }
    >
      <form onSubmit={save} className="space-y-4 px-3 pb-5">
        {/* Length caps keep an edited glossary from crowding out the rest of the model's instructions. */}
        <Textarea
          label="Definition"
          required
          rows={4}
          maxLength={600}
          disabled={readOnly}
          value={definition}
          onChange={(e) => {
            setDefinition(e.target.value)
            setState('idle')
          }}
        />
        <Input
          label="Other names for it, separated by commas"
          type="text"
          maxLength={200}
          disabled={readOnly}
          value={synonyms}
          onChange={(e) => {
            setSynonyms(e.target.value)
            setState('idle')
          }}
        />
        {metric.required_roles.length > 0 && (
          <p className="text-body-sm text-steel">Needs these kinds of column: {metric.required_roles.map((role) => role.replaceAll('_', ' ')).join(', ')}.</p>
        )}
        {/* Folded: a SQL template with {placeholders} is for the engineer, and open it sat between
            the analyst and the Save button. */}
        <Expander
          chevronAtEnd
          summaryClassName="px-0 py-2 hover:bg-transparent"
          label={<span className="text-body-sm font-bold text-charcoal">How it is calculated</span>}
        >
          <pre className="mt-1 rounded-xl bg-surface-soft p-4 text-code break-words whitespace-pre-wrap text-ink">{metric.sql_pattern}</pre>
        </Expander>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" size="sm" loading={state === 'saving'} disabled={readOnly || !changed || problem !== null}>
            Save definition
          </Button>
          {/* One live region per entry, always in the DOM: a span added at save time is announced late or not at all. */}
          <span role="status" className={cx('min-w-0 text-body-sm font-bold break-words', problem ? 'text-attention' : 'text-success')}>
            {problem ?? (state === 'saved' && 'Saved')}
          </span>
        </div>
      </form>
    </Expander>
  )
}

export default function Glossary({ glossary, readOnly, onSave }: GlossaryProps) {
  if (glossary.length === 0) return <p className="measure text-body-md text-slate">No metric definitions are loaded for these files.</p>
  return (
    <div>
      <p className="measure text-body-sm text-slate">
        “Attrition” can be counted three ways, so DarwinLens answers with the definitions below — change them to match your company.
      </p>
      <div className="-mx-3 mt-3">
        {glossary.map((metric) => (
          <MetricEditor key={metric.key} metric={metric} glossary={glossary} readOnly={readOnly} onSave={onSave} />
        ))}
      </div>
    </div>
  )
}
