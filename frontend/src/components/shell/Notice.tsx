// The one place the shell reports a problem. Every problem is two plain sentences: what happened,
// then what to do next. Nothing technical (status codes, stack traces) is ever shown.

export interface Problem {
  /** What happened. Line breaks are kept, so several skipped files read as one line each. */
  message: string
  /** Empty when the message already says what to do. */
  nextStep: string
  /** `warn`: the app carried on (a skipped file, an expired session). `bad`: the action failed. */
  tone: 'warn' | 'bad'
}

interface NoticeProps {
  problem: Problem
  onDismiss: () => void
}

export default function Notice({ problem, onDismiss }: NoticeProps) {
  const colours = problem.tone === 'bad' ? 'border-bad/30 bg-bad-soft text-bad' : 'border-warn/30 bg-warn-soft text-warn'
  return (
    <div role="alert" className={`flex items-start gap-3 rounded-card border px-4 py-3 text-sm ${colours}`}>
      <p className="min-w-0 flex-1 break-words">
        <span className="font-semibold whitespace-pre-line">{problem.message}</span>
        {problem.nextStep && <span className="text-ink"> {problem.nextStep}</span>}
      </p>
      <button type="button" onClick={onDismiss} className="shrink-0 rounded px-1 font-medium underline underline-offset-2">
        Dismiss
      </button>
    </div>
  )
}
