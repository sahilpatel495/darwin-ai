// The Links tab: how the uploaded files connect. Detected links (the same person in two files)
// and combined views (files with the same columns, stacked). Each is a guess made from the data,
// so each is written as a sentence with its evidence in it, and each can be kept or removed.
// A removed link is never used in an answer.

import { useEffect, useRef, useState } from 'react'
import { labelOf } from '../../lib/tables'
import type { Catalog } from '../../types'
import type { Explanation } from '../education/explain'
import { EXPLAIN } from '../education/explain'
import { Button, RuledRow, WhatsThis, cx } from '../ui'
import type { LinkLine } from './wording'
import { linkLine, unionLine } from './wording'

type LinkStatus = 'active' | 'suggested' | 'rejected'

interface LinksProps {
  catalog: Catalog
  /** Files are not loaded: the links still read, but the server cannot be told about a change. */
  readOnly: boolean
  onSetLink: (linkId: string, status: 'active' | 'rejected') => Promise<void>
}

interface LinkRowProps extends Pick<LinksProps, 'readOnly' | 'onSetLink'> {
  id: string
  line: LinkLine
  status: LinkStatus
  /** "link" or "combined view": the word inside each button's accessible name. */
  noun: string
}

function LinkRow({ id, line, status, noun, readOnly, onSetLink }: LinkRowProps) {
  const [saving, setSaving] = useState(false)
  const actions = useRef<HTMLDivElement>(null)
  const pressed = useRef(false)
  const set = async (next: 'active' | 'rejected') => {
    if (saving) return
    pressed.current = true
    setSaving(true)
    await onSetLink(id, next) // the sidebar reports any failure; the row only needs to re-enable
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

  // In use needs no word while the Remove button is there to say it; read-only has no button, so
  // the state has to be written out.
  const note = status === 'rejected' ? 'Not used in answers' : status === 'suggested' ? 'Suggested' : readOnly ? 'In use' : null

  return (
    // flex-col only: RuledRow's own gap and alignment are utilities too, and a second utility for
    // the same property would be decided by stylesheet order rather than by this file.
    <RuledRow as="li" className="flex-col">
      <p className={cx('type-body', status === 'rejected' ? 'text-ink-soft' : 'text-ink')}>{line.sentence}</p>
      <div ref={actions} className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {note && <span className="type-small text-ink-soft">{note}</span>}
        {!readOnly && status !== 'active' && (
          <Button size="sm" aria-disabled={saving} className={cx(saving && 'opacity-55')} onClick={() => set('active')} aria-label={`Keep the ${noun} between ${line.pair}`}>
            Keep
          </Button>
        )}
        {!readOnly && status !== 'rejected' && (
          <Button size="sm" aria-disabled={saving} className={cx(saving && 'opacity-55')} onClick={() => set('rejected')} aria-label={`Remove the ${noun} between ${line.pair}`}>
            Remove
          </Button>
        )}
      </div>
    </RuledRow>
  )
}

function Heading({ children, explain }: { children: string; explain: Explanation }) {
  return (
    // The "?" sits at the right edge and opens leftwards: the panel is as wide as this column,
    // so anywhere else it would be clipped by the sidebar's own scroller.
    <div className="flex items-center justify-between gap-2 pt-1">
      <h3 className="type-title text-ink">{children}</h3>
      <WhatsThis {...explain} align="right" />
    </div>
  )
}

export default function Links({ catalog, readOnly, onSetLink }: LinksProps) {
  const name = (table: string) => labelOf(table, catalog.tables)
  // The server lists links in use first, so a removed link would jump down the list the moment it
  // is clicked and leave another link's Remove button under the cursor. A fixed order keeps every
  // row where it was.
  const relationships = [...catalog.relationships].sort((a, b) => a.id.localeCompare(b.id))

  if (relationships.length === 0 && catalog.unions.length === 0) {
    return <p className="pt-3 type-body text-ink-soft">No links were found between these files, so each question will use one file at a time.</p>
  }

  return (
    <div className="space-y-4">
      {relationships.length > 0 && (
        <section>
          <Heading explain={EXPLAIN.links}>Links between your files</Heading>
          <ul>
            {relationships.map((link) => (
              <LinkRow key={link.id} id={link.id} line={linkLine(link, name)} status={link.status} noun="link" readOnly={readOnly} onSetLink={onSetLink} />
            ))}
          </ul>
        </section>
      )}
      {catalog.unions.length > 0 && (
        <section>
          <Heading explain={EXPLAIN.combined}>Combined views</Heading>
          <ul>
            {catalog.unions.map((union) => (
              <LinkRow key={union.id} id={union.id} line={unionLine(union, name)} status={union.status} noun="combined view" readOnly={readOnly} onSetLink={onSetLink} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
