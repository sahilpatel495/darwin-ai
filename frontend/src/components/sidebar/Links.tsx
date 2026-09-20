// How the uploaded files connect: detected joins (relationships) and stacked same-shape files
// (unions). Each is a guess made from the data, so each shows its evidence and can be confirmed or
// rejected. A rejected link is never used in an answer.

import { useEffect, useRef, useState } from 'react'
import type { Catalog } from '../../types'
import { linkExplanation, linkLabel, unionLabel } from './wording'

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
  status: LinkStatus
  onSetLink: LinksProps['onSetLink']
}

function LinkRow({ id, label, explanation, status, onSetLink }: LinkRowProps) {
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
      <p className={`font-mono text-xs leading-relaxed break-words text-ink ${status === 'rejected' ? 'line-through decoration-ink-faint' : ''}`}>
        {label}
      </p>
      <p className="mt-1 text-xs leading-relaxed break-words text-ink-soft">{explanation}</p>
      <div ref={actions} className="mt-2 flex items-center gap-2">
        <span className={`mr-auto rounded-full px-2 py-0.5 text-xs font-medium ${chip.colours}`}>{chip.text}</span>
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
  const { relationships, unions } = catalog
  if (relationships.length === 0 && unions.length === 0) {
    return <p className="text-sm text-ink-soft">No links were found between these files, so each question will use one file at a time.</p>
  }
  return (
    <ul className="space-y-2">
      {relationships.map((link) => (
        <LinkRow key={link.id} id={link.id} label={linkLabel(link)} explanation={linkExplanation(link)} status={link.status} onSetLink={onSetLink} />
      ))}
      {unions.map((union) => (
        <LinkRow
          key={union.id}
          id={union.id}
          label={unionLabel(union)}
          explanation={`These files have the same columns, so they are stacked into one table called ${union.view_name}.`}
          status={union.status}
          onSetLink={onSetLink}
        />
      ))}
    </ul>
  )
}
