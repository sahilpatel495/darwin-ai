// How the uploaded files connect: detected joins (relationships) and stacked same-shape files
// (unions). Each is a guess made from the data, so each shows its evidence and can be confirmed or
// rejected. A rejected link is never used in an answer.

import { useEffect, useRef, useState } from 'react'
import { labelOf } from '../../lib/tables'
import type { Catalog } from '../../types'
import { linkExplanation, linkLabel, matchPercent, unionLabel } from './wording'

type LinkStatus = 'active' | 'suggested' | 'rejected'

interface LinksProps {
  catalog: Catalog
  onSetLink: (linkId: string, status: 'active' | 'rejected') => Promise<void>
}

const STATUS_CHIP: Record<LinkStatus, { text: string; colours: string }> = {
  active: { text: 'In use', colours: 'bg-good-soft text-good' },
  suggested: { text: 'Suggested', colours: 'bg-warn-soft text-warn' },
  rejected: { text: 'Not used', colours: 'bg-sunken text-ink-soft' },
}

const smallButton = 'rounded-md border border-line px-2.5 py-1 text-xs font-medium text-ink hover:border-accent hover:text-accent aria-disabled:opacity-50'

interface LinkRowProps {
  id: string
  label: string
  explanation: string
  /** Shown beside the status, e.g. "100% match". Unions have none: their columns match by definition. */
  evidence?: string
  status: LinkStatus
  onSetLink: LinksProps['onSetLink']
}

function LinkRow({ id, label, explanation, evidence, status, onSetLink }: LinkRowProps) {
  const [saving, setSaving] = useState(false)
  const actions = useRef<HTMLDivElement>(null)
  const pressed = useRef(false)
  const set = async (next: 'active' | 'rejected') => {
    if (saving) return
    pressed.current = true
    setSaving(true)
    await onSetLink(id, next) // the shell reports any failure; the row only needs to re-enable
    setSaving(false)
  }
  // Once the status flips, the button that was pressed is gone (the row then offers only the
  // opposite action) and keyboard focus would fall back to the top of the page. Hand it to the
  // button that remains. The buttons are aria-disabled while saving, not disabled, for the same
  // reason: a disabled button drops focus too.
  useEffect(() => {
    if (saving || !pressed.current) return
    pressed.current = false
    if (!actions.current?.contains(document.activeElement)) actions.current?.querySelector('button')?.focus()
  }, [saving, status])
  const chip = STATUS_CHIP[status]

  return (
    <li className="rounded-card border border-line bg-surface p-3">
      <p className={`text-sm leading-snug font-medium break-words text-ink ${status === 'rejected' ? 'line-through decoration-ink-faint' : ''}`}>
        {label}
      </p>
      <p className="mt-1 text-xs leading-relaxed break-words text-ink-soft">{explanation}</p>
      <div ref={actions} className="mt-2 flex items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${chip.colours}`}>{chip.text}</span>
        <span className="mr-auto text-xs text-ink-soft">{evidence}</span>
        {status !== 'active' && (
          <button type="button" aria-disabled={saving} onClick={() => set('active')} aria-label={`Confirm link ${label}`} className={smallButton}>
            Confirm
          </button>
        )}
        {status !== 'rejected' && (
          <button type="button" aria-disabled={saving} onClick={() => set('rejected')} aria-label={`Reject link ${label}`} className={smallButton}>
            Reject
          </button>
        )}
      </div>
    </li>
  )
}

export default function Links({ catalog, onSetLink }: LinksProps) {
  const { unions } = catalog
  const name = (table: string) => labelOf(table, catalog.tables)
  // The server lists links in use first, so a rejected link would jump down the list the moment
  // it is clicked and leave another link's Reject button under the cursor. A fixed order keeps
  // every row where it was.
  const relationships = [...catalog.relationships].sort((a, b) => a.id.localeCompare(b.id))
  if (relationships.length === 0 && unions.length === 0) {
    return <p className="text-sm text-ink-soft">No links were found between these files, so each question will use one file at a time.</p>
  }
  return (
    <ul className="space-y-2">
      {relationships.map((link) => (
        <LinkRow
          key={link.id}
          id={link.id}
          label={linkLabel(link, name)}
          explanation={linkExplanation(link, name)}
          evidence={`${matchPercent(link)}% match`}
          status={link.status}
          onSetLink={onSetLink}
        />
      ))}
      {unions.map((union) => (
        <LinkRow
          key={union.id}
          id={union.id}
          label={unionLabel(union, name)}
          explanation={`These files have the same columns, so questions that span them read one stacked table (${union.view_name} in the SQL).`}
          status={union.status}
          onSetLink={onSetLink}
        />
      ))}
    </ul>
  )
}
