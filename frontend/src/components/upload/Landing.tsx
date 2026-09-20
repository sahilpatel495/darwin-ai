// First screen, shown until the session has tables. Its job: get a first-time analyst to a
// charted answer in under 30 seconds, which is why the sample-data button sits right under the
// drop zone instead of behind a link.

import DropZone from './DropZone'
import UploadProgress from './UploadProgress'
import type { Busy } from './UploadProgress'

interface LandingProps {
  busy: Busy | null
  onFiles: (files: File[]) => void
  onSample: () => void
}

// Not a sequence, so no numbering: three promises the rest of the app has to keep.
const PROOF_POINTS = [
  ['Your rows never reach the model.', 'The AI is shown column names and statistics. Values in personal data columns are never sent.'],
  ['Every number is computed by a database.', 'The AI writes the query. A database does the arithmetic, so totals are exact.'],
  ['Every answer shows its work.', 'See how the question was read, the query that ran, and what was sent to the model.'],
]

export default function Landing({ busy, onFiles, onSample }: LandingProps) {
  // Source order is headline, actions, proof points, so on a phone the upload stays above the
  // fold. On wide screens the grid lifts the actions into a right-hand column beside both.
  return (
    <div className="mx-auto grid w-full max-w-5xl gap-x-14 gap-y-10 px-4 py-10 sm:px-6 sm:py-16 lg:grid-cols-[1fr_26rem]">
      <div>
        <h1 className="text-4xl leading-[1.08] font-semibold tracking-tight text-ink sm:text-5xl">
          Ask your spreadsheets.
          <br />
          Verify every answer.
        </h1>
        <p className="mt-5 max-w-[52ch] text-base leading-relaxed text-ink-soft">
          Upload your HR exports as they are, title rows, ₹ symbols and all. Ask a question in plain English and get a number you can
          stand behind, with the steps that produced it.
        </p>
      </div>

      <div className="space-y-4 lg:col-start-2 lg:row-span-2 lg:row-start-1">
        {busy ? <UploadProgress busy={busy} /> : <DropZone onFiles={onFiles} />}
        <div className="rounded-card border border-line bg-surface p-4">
          <p className="text-sm text-ink-soft">No file to hand? Explore with a made-up company of 500 employees.</p>
          <button
            type="button"
            onClick={onSample}
            disabled={busy !== null}
            className="mt-3 w-full rounded-md border border-accent px-4 py-2 text-sm font-medium text-accent hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-60"
          >
            Try with sample HR data
          </button>
        </div>
      </div>

      <dl className="max-w-[56ch] lg:col-start-1">
        {PROOF_POINTS.map(([claim, detail]) => (
          <div key={claim} className="border-t border-line py-4">
            <dt className="font-medium text-ink">{claim}</dt>
            <dd className="mt-1 text-sm leading-relaxed text-ink-soft">{detail}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
