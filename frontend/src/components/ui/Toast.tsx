import { useEffect, useState } from 'react'
import { CheckIcon, CloseIcon } from './icons'
import { cx } from './cx'

export interface ToastMessage {
  id: number
  text: string
  tone: 'done' | 'error'
}

type Listener = (messages: ToastMessage[]) => void

let messages: ToastMessage[] = []
const listeners = new Set<Listener>()
let nextId = 1

const publish = () => listeners.forEach((listener) => listener(messages))

function dismiss(id: number) {
  messages = messages.filter((message) => message.id !== id)
  publish()
}

/**
 * Say that something quiet worked: "Saved to board", "Link removed". Never for anything the
 * analyst must read — that is a Banner, which stays on the page.
 *
 * A module-level list rather than a context, because a toast is raised from click handlers deep
 * in five different screens and none of them should have to be wrapped in a provider.
 * ponytail: no queue limit; if a screen ever raises dozens, cap the list here.
 */
export function toast(text: string, tone: ToastMessage['tone'] = 'done'): void {
  const id = nextId++
  messages = [...messages, { id, text, tone }]
  publish()
  setTimeout(() => dismiss(id), tone === 'error' ? 6000 : 3500)
}

/** Mounted once, at the root. Renders whatever `toast()` has raised. */
export default function Toaster() {
  const [shown, setShown] = useState<ToastMessage[]>(messages)

  useEffect(() => {
    listeners.add(setShown)
    return () => {
      listeners.delete(setShown)
    }
  }, [])

  if (shown.length === 0) return null

  return (
    <div
      // `status`, not `alert`: a confirmation should not interrupt what is being read.
      role="status"
      aria-live="polite"
      className="print-hide pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 pb-[calc(env(safe-area-inset-bottom,0px)+4.5rem)] md:pb-6"
    >
      {shown.map((message) => (
        <div
          key={message.id}
          className={cx(
            'toast-in pointer-events-auto flex max-w-[min(28rem,calc(100vw-2rem))] items-center gap-2.5',
            'rounded-pill py-2 pr-2 pl-3.5 type-small font-medium shadow-3',
            message.tone === 'error' ? 'bg-red text-white' : 'bg-ink text-wash',
          )}
        >
          {message.tone === 'done' && <CheckIcon size={16} className="shrink-0 text-green" />}
          <span className="min-w-0">{message.text}</span>
          <button
            type="button"
            onClick={() => dismiss(message.id)}
            aria-label="Dismiss"
            className="-my-1 shrink-0 rounded-pill p-1 opacity-70 hover:opacity-100"
          >
            <CloseIcon size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
