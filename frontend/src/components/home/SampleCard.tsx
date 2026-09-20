// The way in for someone with nothing to upload (§8). First card on the shelf, so it is never
// below the fold once a project or two exists — and the one card on Home that is tinted, because
// it is the only one that is an invitation rather than a record of work already done.

import { useState } from 'react'
import { Glyph } from '../graphics'
import { Button, Card } from '../ui'
import { SAMPLE_ZIP_URL } from './sample'
import SampleFilesDialog from './SampleFilesDialog'

interface SampleCardProps {
  onSample: () => void
  /** Something else is already loading: two uploads at once would fight over the one session. */
  busy: boolean
}

export default function SampleCard({ onSample, busy }: SampleCardProps) {
  const [open, setOpen] = useState(false)

  return (
    <Card as="article" tone="soft" className="flex min-w-0 flex-col gap-4">
      <Glyph name="people" size={40} className="text-ink-deep" accent="var(--color-purple)" />
      <div>
        <h2 className="text-heading-sm text-ink-deep">Sample company</h2>
        <p className="mt-2 text-body-sm text-slate">
          Spreadsheets from a company that does not exist: people, a salary register, attendance, reviews and sales. Messy on purpose, so you can see
          what DarwinLens does about it.
        </p>
      </div>
      <div className="mt-auto flex flex-wrap items-center gap-2">
        <Button variant="primary" size="sm" loading={busy} onClick={onSample}>
          Open the sample company
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
          See what&rsquo;s inside
        </Button>
        <a href={SAMPLE_ZIP_URL} download className="px-2 text-body-sm text-primary-deep">
          Download all
        </a>
      </div>

      <SampleFilesDialog open={open} onClose={() => setOpen(false)} onLoad={onSample} busy={busy} />
    </Card>
  )
}
