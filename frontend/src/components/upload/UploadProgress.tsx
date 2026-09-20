// What the analyst sees while files travel and are cleaned: a progress bar, one sentence saying
// which stage we are in, and skeleton cards standing in for the file cards to come.
// The bar is two divs rather than <progress>: the native element ignores the design tokens and
// draws a heavy grey track on macOS.

/** The one long-running action the shell can be in. `fraction` is 0..1 of bytes sent. */
export type Busy = { kind: 'upload'; files: number; fraction: number } | { kind: 'sample' }

function sentence(busy: Busy): string {
  if (busy.kind === 'sample') return 'Loading the sample HR data…'
  const files = busy.files === 1 ? '1 file' : `${busy.files} files`
  // Once every byte is sent the server is still reading and cleaning, which can take longer than the upload.
  return busy.fraction < 1 ? `Uploading ${files}… ${Math.round(busy.fraction * 100)}%` : `Reading and cleaning ${files}…`
}

export default function UploadProgress({ busy }: { busy: Busy }) {
  // Only the byte transfer has a known length. Everything else pulses to say "working".
  const percent = busy.kind === 'upload' && busy.fraction < 1 ? Math.round(busy.fraction * 100) : null
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <p className="text-sm font-medium text-ink">{sentence(busy)}</p>
      <div role="progressbar" aria-label="Progress" aria-valuenow={percent ?? undefined} className="h-2 overflow-hidden rounded-full bg-accent-soft">
        <div
          className={`h-full rounded-full bg-accent transition-[width] ${percent === null ? 'animate-pulse' : ''}`}
          style={{ width: `${percent ?? 100}%` }}
        />
      </div>
      <div aria-hidden className="space-y-2">
        {[0, 1].map((i) => (
          <div key={i} className="animate-pulse space-y-2 rounded-card border border-line bg-surface p-3">
            <div className="h-3 w-2/3 rounded bg-sunken" />
            <div className="h-3 w-1/3 rounded bg-sunken" />
          </div>
        ))}
      </div>
    </div>
  )
}
