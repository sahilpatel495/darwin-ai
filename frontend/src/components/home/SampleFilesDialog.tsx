// "See what's inside" (§15): the sample files, what each one holds, how big it is, and a way to
// open any of them before agreeing to load them. Used from the landing page and from the sample
// card on Home.
//
// The listing is fetched here rather than through api.ts, which is Lead-owned and does not carry
// this call yet. A server without the endpoint is not an error — the dialog says so in a sentence
// and shows no download links, because a dead link is worse than no link.

import { useEffect, useState } from 'react'
import { Button, Dialog, ListRow, Skeleton } from '../ui'
import { fileSize, parseSampleFiles, SAMPLE_FILES_URL, SAMPLE_ZIP_URL, sampleFileUrl } from './sample'
import type { SampleFile } from './sample'

interface SampleFilesDialogProps {
  open: boolean
  onClose: () => void
  /** Loads the sample into a new project. The dialog closes itself first. */
  onLoad: () => void
  /** Something else is already loading: two uploads at once would fight over the one session. */
  busy: boolean
}

type Listing = { state: 'loading' } | { state: 'ready'; files: SampleFile[] } | { state: 'unavailable' }

export default function SampleFilesDialog({ open, onClose, onLoad, busy }: SampleFilesDialogProps) {
  const [listing, setListing] = useState<Listing>({ state: 'loading' })

  useEffect(() => {
    if (!open) return
    let live = true
    setListing({ state: 'loading' })
    fetch(SAMPLE_FILES_URL, { headers: { Accept: 'application/json' } })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('no listing'))))
      .then((body: unknown) => {
        if (!live) return
        const files = parseSampleFiles(body)
        setListing(files.length ? { state: 'ready', files } : { state: 'unavailable' })
      })
      .catch(() => {
        if (live) setListing({ state: 'unavailable' })
      })
    return () => {
      live = false
    }
  }, [open])

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="What is in the sample"
      description="The same kind of files you would upload yourself, messy on purpose."
      footer={
        <>
          {listing.state === 'ready' && (
            <a href={SAMPLE_ZIP_URL} download className="mr-auto type-small">
              Download all (zip)
            </a>
          )}
          <Button onClick={onClose}>Close</Button>
          <Button
            variant="primary"
            disabled={busy}
            onClick={() => {
              onClose()
              onLoad()
            }}
          >
            Load this data
          </Button>
        </>
      }
    >
      {listing.state === 'loading' && (
        <div role="status" aria-label="Reading the sample files" className="space-y-2.5">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-3/4" />
        </div>
      )}

      {listing.state === 'unavailable' && (
        <p className="type-body text-ink-2">
          This server does not hand out the sample files on their own. Choose Load this data to open them in a project, where every file lists what was
          read and what was cleaned.
        </p>
      )}

      {listing.state === 'ready' && (
        <ul>
          {listing.files.map((file) => (
            <ListRow as="li" key={file.name} className="items-baseline justify-between gap-4">
              <span className="min-w-0 flex-1">
                <a href={sampleFileUrl(file.name)} download className="type-body font-medium">
                  {file.name}
                </a>
                {file.description && <span className="block type-small text-ink-2">{file.description}</span>}
              </span>
              <span className="tnum shrink-0 type-small text-ink-2">{fileSize(file.size)}</span>
            </ListRow>
          ))}
        </ul>
      )}
    </Dialog>
  )
}
