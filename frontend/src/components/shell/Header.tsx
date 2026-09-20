// Top bar: brand, the privacy promise with its explainer, the Trust Report link and "New session".
// The explainer is a native <dialog>: focus trapping, Esc to close and the backdrop come for free.

import { useRef } from 'react'
import { ShieldIcon } from './icons'

interface HeaderProps {
  onTrustPage: boolean
  onNewSession: () => void
  /**
   * True while files are uploading or being read. "New session" waits for that to finish: the
   * upload cannot be cancelled on the server, so starting over mid-way would only make a slow
   * server read the same files twice.
   */
  working: boolean
  /** True while the phone drawer covers the page, so Tab cannot land on a control nobody can see. */
  behindDrawer: boolean
}

const quietButton = 'rounded-md px-2.5 py-1.5 text-sm font-medium text-ink-soft hover:bg-sunken hover:text-ink disabled:cursor-not-allowed disabled:opacity-50'

export default function Header({ onTrustPage, onNewSession, working, behindDrawer }: HeaderProps) {
  const explainer = useRef<HTMLDialogElement>(null)

  return (
    <header inert={behindDrawer} className="shrink-0 border-b border-line bg-surface">
      <div className="flex flex-wrap items-center gap-x-1 gap-y-1 px-3 py-2 sm:px-5">
        <a href="#/" className="mr-auto rounded px-1 text-lg font-semibold tracking-tight text-ink">
          Verity
        </a>

        <button
          type="button"
          onClick={() => explainer.current?.showModal()}
          aria-haspopup="dialog"
          className="flex items-center gap-1.5 rounded-full border border-good/30 bg-good-soft px-2.5 py-1 text-sm font-medium text-good"
        >
          <ShieldIcon />
          <span className="max-sm:sr-only">Your rows never reach the model</span>
        </button>

        <a href={onTrustPage ? '#/' : '#/trust'} className={quietButton}>
          {onTrustPage ? 'Back to questions' : 'Trust Report'}
        </a>
        <button type="button" onClick={onNewSession} disabled={working} className={quietButton}>
          New session
        </button>
      </div>

      <dialog
        ref={explainer}
        aria-labelledby="privacy-title"
        className="m-auto w-[min(34rem,calc(100vw-2rem))] rounded-card border border-line bg-surface p-0 text-ink backdrop:bg-ink/40"
      >
        <div className="space-y-3 p-5 text-sm leading-relaxed text-ink-soft">
          <h2 id="privacy-title" className="text-lg font-semibold text-ink">
            Your rows never reach the model
          </h2>
          <p>
            Verity uses an AI model for two jobs only: turning your question into a database query, and wording the result. Every number is
            calculated by a database running inside this app, never by the model.
          </p>
          <p>
            <span className="font-medium text-ink">What the model is shown:</span> table and column names, column types and summary
            statistics. For a column with a few repeated values, such as department or location, it also gets the list of values so it can
            filter correctly. To word an answer it is shown the query&rsquo;s result, with personal values replaced by placeholders.
          </p>
          <p>
            <span className="font-medium text-ink">What it is never shown:</span> the rows of your files, or any value from a column that
            holds personal data such as names, emails, phone numbers, PAN or Aadhaar. Each file&rsquo;s Data Health receipt lists the columns
            that were hidden.
          </p>
          <p>
            You can check this yourself. Under any answer, open &ldquo;How I got this&rdquo; and then &ldquo;What the model saw&rdquo; to read
            exactly what was sent.
          </p>
          <form method="dialog" className="pt-1 text-right">
            <button className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-ink">Close</button>
          </form>
        </div>
      </dialog>
    </header>
  )
}
