import { useEffect, useId, useRef } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { cx } from './cx'

export interface DialogProps {
  open: boolean
  /** Called for every way out: the close button, Esc, and a click on the backdrop. */
  onClose: () => void
  /** Names the dialog and is rendered as its heading. Sentence case. */
  title: string
  children: ReactNode
  /** Buttons along the bottom, right-aligned. The confirming one goes last. */
  footer?: ReactNode
  /** `sm` 26rem · `md` 34rem · `lg` 46rem. */
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const WIDTH = { sm: 'w-[26rem]', md: 'w-[34rem]', lg: 'w-[46rem]' } as const

/**
 * The native <dialog>, which already traps focus, closes on Esc and hands focus back to
 * whatever opened it. All this adds is the React open/close bridge, a backdrop click and
 * the labelling.
 */
export default function Dialog({ open, onClose, title, children, footer, size = 'md', className }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const el = ref.current
    if (!el) return
    // showModal() on an open dialog throws; close() on a closed one is a no-op that still
    // fires nothing. Guard both so a re-render never breaks the dialog.
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])

  // A click on the backdrop lands on the <dialog> element itself, never on the inner box.
  const onBackdropClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === ref.current) onClose()
  }

  return (
    <dialog ref={ref} aria-labelledby={titleId} onClose={onClose} onClick={onBackdropClick} className={className}>
      <div className={cx('flex max-h-[inherit] max-w-full flex-col', WIDTH[size])}>
        <div className="flex items-start gap-4 border-b border-rule px-5 py-4">
          <h2 id={titleId} className="min-w-0 flex-1 type-statement text-ink">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-mr-1 -mt-1 shrink-0 rounded-control px-2 py-1 text-ink-soft hover:bg-wash hover:text-ink"
          >
            <svg aria-hidden width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 2 12 12M12 2 2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 type-body text-ink">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-rule px-5 py-3">{footer}</div>}
      </div>
    </dialog>
  )
}
