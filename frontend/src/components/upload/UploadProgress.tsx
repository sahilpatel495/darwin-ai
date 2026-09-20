// What the analyst sees while files travel and are cleaned: one sentence saying which stage we are
// in and a bar for the part that has a known length. The bar is two divs rather than <progress>:
// the native element ignores the tokens and draws a heavy grey track on macOS.

import { useEffect, useState } from 'react'
import { cx } from '../ui'

/** The one long-running action a screen can be in. `fraction` is 0..1 of bytes sent. */
export type Busy = { kind: 'upload'; files: number; fraction: number } | { kind: 'sample' }

function sentence(busy: Busy): string {
  if (busy.kind === 'sample') return 'Loading the sample company…'
  const files = busy.files === 1 ? '1 file' : `${busy.files} files`
  // Once every byte is sent the server is still reading and cleaning, which can take longer than the upload.
  return busy.fraction < 1 ? `Uploading ${files}… ${Math.round(busy.fraction * 100)}%` : `Reading and cleaning ${files}…`
}

export default function UploadProgress({ busy, className }: { busy: Busy; className?: string }) {
  // The hosted demo sleeps when idle and takes about a minute to wake. A bar that just sits there
  // looks broken long before that, so after six seconds the wait is explained in words.
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 6000)
    return () => clearTimeout(timer)
  }, [])

  // Only the byte transfer has a known length. Everything else fills the bar and pulses.
  const percent = busy.kind === 'upload' && busy.fraction < 1 ? Math.round(busy.fraction * 100) : null

  return (
    <div role="status" aria-live="polite" className={cx('space-y-2', className)}>
      <p className="text-body-md font-bold text-ink-deep">{sentence(busy)}</p>
      <div role="progressbar" aria-label="Progress" aria-valuenow={percent ?? undefined} className="h-2 overflow-hidden rounded-full bg-surface-soft">
        <div
          className={cx('h-full rounded-full bg-primary transition-[width] duration-200 ease-[var(--ease-spring)]', percent === null && 'animate-pulse')}
          style={{ width: `${percent ?? 100}%` }}
        />
      </div>
      {slow && <p className="text-body-sm text-steel">The server sleeps when nobody is using it, so the first load can take about a minute.</p>}
    </div>
  )
}
