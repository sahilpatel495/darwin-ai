// The HR glossary: what "attrition" or "headcount" means in this session. Companies disagree on
// these definitions, so the analyst can edit the wording and the synonyms. The SQL pattern is
// shown read-only: it is what actually computes the metric, and changing it safely is an
// engineer's job, not a text box's.

import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Metric } from '../../types'
import Expander from './Expander'
import { metricProblem, parseSynonyms } from './wording'

interface GlossaryProps {
  glossary: Metric[]
  /** Resolves true when saved. The shell reports failures, so this only drives the "Saved" note. */
  onSave: (glossary: Metric[]) => Promise<boolean>
}

const field = 'mt-1 block w-full rounded-md border border-line bg-surface px-2.5 py-1.5 text-sm text-ink'

function MetricEditor({ metric, glossary, onSave }: GlossaryProps & { metric: Metric }) {
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
    <Expander label={metric.name}>
      <form onSubmit={save} className="space-y-3 pt-1 pb-3">
        <label className="block text-xs font-medium text-ink-soft">
          Definition
          {/* Length caps keep an edited glossary from crowding out the rest of the model's instructions. */}
          {/* field-sizing: the box grows to fit the definition, so nobody scrolls a four-line box inside a scrolling sidebar. */}
          <textarea
            required
            rows={4}
            maxLength={600}
            value={definition}
            onChange={(e) => {
              setDefinition(e.target.value)
              setState('idle')
            }}
            className={`${field} [field-sizing:content]`}
          />
        </label>
        <label className="block text-xs font-medium text-ink-soft">
          Also called (separate with commas)
          <input
            type="text"
            maxLength={200}
            value={synonyms}
            onChange={(e) => {
              setSynonyms(e.target.value)
              setState('idle')
            }}
            className={field}
          />
        </label>
        {metric.required_roles.length > 0 && (
          <p className="text-xs text-ink-soft">Needs these kinds of column: {metric.required_roles.map((role) => role.replaceAll('_', ' ')).join(', ')}.</p>
        )}
        {/* Folded by default: a SQL template with {placeholders} is for the engineer, and it sat
            between the analyst and the Save button. A plain <details>, because Expanders must not nest. */}
        <details>
          <summary className="cursor-pointer text-xs font-medium text-accent-ink">How it is calculated (SQL pattern)</summary>
          <pre className="mt-1 rounded-md bg-sunken p-2 font-mono text-xs break-words whitespace-pre-wrap text-ink">{metric.sql_pattern}</pre>
        </details>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={!changed || problem !== null || state === 'saving'}
            className="shrink-0 rounded-md bg-accent px-3 py-1.5 text-xs font-medium whitespace-nowrap text-white hover:bg-accent-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            {state === 'saving' ? 'Saving…' : 'Save definition'}
          </button>
          <span role="status" className={`min-w-0 text-xs break-words ${problem ? 'text-warn' : 'text-good'}`}>
            {problem ?? (state === 'saved' && 'Saved. New questions will use this definition.')}
          </span>
        </div>
      </form>
    </Expander>
  )
}

export default function Glossary({ glossary, onSave }: GlossaryProps) {
  if (glossary.length === 0) return <p className="text-sm text-ink-soft">No metric definitions are loaded for this session.</p>
  return (
    <div className="rounded-card border border-line bg-surface px-3 pb-1 [&>details:first-child]:border-t-0">
      {glossary.map((metric) => (
        <MetricEditor key={metric.key} metric={metric} glossary={glossary} onSave={onSave} />
      ))}
    </div>
  )
}
