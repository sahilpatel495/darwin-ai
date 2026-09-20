// The way in for someone with nothing to upload (§15). First card on the shelf, so it is never
// below the fold once a project or two exists.

import { useState } from 'react'
import { Button, Card } from '../ui'
import SampleFilesDialog from './SampleFilesDialog'

interface SampleCardProps {
  onSample: () => void
  /** Something else is already loading: two uploads at once would fight over the one session. */
  busy: boolean
}

export default function SampleCard({ onSample, busy }: SampleCardProps) {
  const [open, setOpen] = useState(false)

  return (
    <Card as="article" className="flex min-w-0 flex-col gap-3 bg-blue-soft shadow-none">
      <h2 className="type-section text-ink">Sample HR company</h2>
      <p className="type-small text-ink-2">
        Spreadsheets from a company that does not exist: people, a salary register, attendance, reviews and sales. Messy on purpose, so you can see what
        Verity does about it.
      </p>
      <div className="mt-auto flex flex-wrap gap-2">
        <Button variant="primary" size="sm" onClick={onSample} disabled={busy}>
          Try with sample HR data
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
          See what&rsquo;s inside
        </Button>
      </div>

      <SampleFilesDialog open={open} onClose={() => setOpen(false)} onLoad={onSample} busy={busy} />
    </Card>
  )
}
