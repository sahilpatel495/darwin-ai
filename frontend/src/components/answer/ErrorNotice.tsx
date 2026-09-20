// Every failure the user sees has the same three parts: what happened, what to do next, and a
// way to do it. Used for thrown ApiErrors, answers of kind "error" and the Trust Report.
interface Props {
  message: string
  nextStep: string
  onRetry?: () => void
}

export default function ErrorNotice({ message, nextStep, onRetry }: Props) {
  return (
    <div role="alert" className="rounded-card border border-bad/30 bg-bad-soft px-4 py-3 text-sm">
      <p className="font-medium text-ink">{message}</p>
      <p className="mt-1 text-ink-soft">{nextStep}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-3 rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:bg-sunken">
          Try again
        </button>
      )}
    </div>
  )
}
