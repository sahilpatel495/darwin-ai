// The Ask tab (§8). Asking is the product, so this screen is only the conversation: the shell
// above owns the files, the drawer and anything that has gone wrong, and this hands the thread
// what it needs to greet the analyst by name and offer them four questions worth asking.

import { useEffect, useRef } from 'react'
import type { ProjectRecord, Turn } from '../../lib/projects'
import type { Suggestion } from '../../lib/suggestions'
import type { Catalog } from '../../types'
import Thread from '../thread/Thread'
import { Skeleton } from '../ui'
import type { PageProps } from './page'

export interface WorkspaceProps extends PageProps {
  catalog: Catalog | null
  /** The catalog is still on its way. The thread waits rather than showing an empty state. */
  loading: boolean
  /** The four questions on the empty screen, chosen for this person's role. */
  suggestions: Suggestion[]
  /** A question sent from another tab or the command palette. Asked once, then forgotten. */
  pendingQuestion: string | null
  onQuestionTaken: () => void
  onSessionExpired: () => void
  /** An answer landed. The shell re-reads the allowance. */
  onAnswered: () => void
}

/**
 * "Ask about this" on a tile, and "ask again" in the command palette, both end here — with a
 * question and no way to hand it over, because the composer belongs to the thread.
 * ponytail: a DOM handshake through the composer's own id. Replace it the day Thread takes an
 * `initialQuestion` of its own; the ids below are the seam.
 */
function askInComposer(question: string) {
  const box = document.querySelector<HTMLTextAreaElement>('#darwinlens-question, #verity-question')
  if (!box) return
  const setValue = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set
  setValue?.call(box, question) // React listens for the input event, not for an assignment to .value
  box.dispatchEvent(new Event('input', { bubbles: true }))
  // A tick for React to have taken the value before the form reads it back.
  setTimeout(() => {
    if (box.form) box.form.requestSubmit()
    else box.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  }, 0)
}

function Loading() {
  return (
    <div role="status" className="mx-auto w-full max-w-[820px] px-4 py-10 sm:px-6">
      <p className="text-body-md text-slate">Loading your files…</p>
      <div aria-hidden className="mt-5 space-y-3">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-8 w-1/2" />
      </div>
    </div>
  )
}

export default function Workspace({
  sessionId,
  project,
  user,
  onOpenData,
  catalog,
  loading,
  suggestions,
  pendingQuestion,
  onQuestionTaken,
  onProjectChange,
  onSessionExpired,
  onAnswered,
}: WorkspaceProps) {
  // The handover waits for the composer to exist — the thread is behind the loading state until
  // the catalog is in — and fires once. Keyed by the question, not a boolean: StrictMode runs this
  // effect twice, and asking twice would cost a model call and leave two identical turns.
  const asked = useRef<string | null>(null)
  useEffect(() => {
    if (!pendingQuestion || !catalog || asked.current === pendingQuestion) return
    asked.current = pendingQuestion
    askInComposer(pendingQuestion)
    onQuestionTaken()
  }, [pendingQuestion, catalog, onQuestionTaken])

  const onTurnsChange = (turns: Turn[]) => {
    const next: ProjectRecord = { ...project, turns }
    onProjectChange(next)
    // A turn is only added once its answer has arrived, which is exactly when the allowance moved.
    if (turns.length > project.turns.length) onAnswered()
  }

  const toggleSaved = (answerId: string) =>
    onProjectChange({
      ...project,
      savedAnswerIds: project.savedAnswerIds.includes(answerId)
        ? project.savedAnswerIds.filter((id) => id !== answerId)
        : [...project.savedAnswerIds, answerId],
    })

  /**
   * The seam with the ask engineer (§11): the greeting and the suggestion cards are theirs to
   * draw and mine to supply. Passed as one object so the wiring compiles on both sides of the
   * change that adds these props to the thread.
   */
  const supplied = {
    heroGreetingName: user?.kind === 'member' ? user.name.trim().split(/\s+/)[0] : undefined,
    suggestions,
    onOpenData,
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      {/* The conversation is one column now that the data panel is a drawer, so the skip link has
          nothing to skip over on a wide screen — but the drawer's dozens of controls are a
          keyboard journey of their own, and this is still the way straight past them. */}
      <button
        type="button"
        onClick={() => document.querySelector<HTMLTextAreaElement>('#darwinlens-question, #verity-question')?.focus()}
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-full focus:bg-canvas focus:px-4 focus:py-2 focus:text-button-md focus:text-primary-deep focus:shadow-level-2"
      >
        Skip to your question
      </button>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        {loading ? (
          <Loading />
        ) : (
          <Thread
            {...supplied}
            sessionId={sessionId}
            catalog={catalog}
            turns={project.turns}
            onTurnsChange={onTurnsChange}
            savedAnswerIds={project.savedAnswerIds}
            onToggleSaved={toggleSaved}
            onSessionExpired={onSessionExpired}
          />
        )}
      </main>
    </div>
  )
}
