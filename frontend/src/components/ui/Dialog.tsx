import { useEffect, useId, useRef } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import IconButton from './IconButton'
import { CloseIcon } from './icons'
import { cx } from './cx'

export interface DialogProps {
  open: boolean
  /** Called for every way out: the close button, Esc, and a click on the backdrop. */
  onClose: () => void
  /** Names the dialog and is rendered as its heading. Sentence case. */
  title: string
  /** One quiet line under the title. */
  description?: string
  children: ReactNode
  /** Buttons along the bottom, right-aligned. The confirming one goes last. */
  footer?: ReactNode
  /** `sm` 26rem · `md` 34rem · `lg` 46rem · `xl` 60rem, for a chart or a table. */
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}

const WIDTH = { sm: 'w-[26rem]', md: 'w-[34rem]', lg: 'w-[46rem]', xl: 'w-[60rem]' } as const

/**
 * The native <dialog>, which already traps focus, closes on Esc and hands focus back to whatever
 * opened it. All this adds is the React open/close bridge, a backdrop click and the labelling.
 */
export default function Dialog({ open, onClose, title, description, children, footer, size = 'md', className }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const el = ref.current
    if (!el) return
    // showModal() on an open dialog throws; close() on a closed one is a no-op. Guard both so a
    // re-render never breaks the dialog.
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
        <div className="flex items-start gap-4 px-5 pt-4 pb-3">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="type-card text-ink">
              {title}
            </h2>
            {description && <p className="mt-1 type-small text-ink-2">{description}</p>}
          </div>
          {/* The label hangs below: this button sits on the dialog's top edge, and a label above it
              would be drawn over the page behind. */}
          <IconButton label="Close" variant="ghost" size="sm" tooltipSide="bottom" onClick={onClose} className="-mt-0.5 -mr-1">
            <CloseIcon size={16} />
          </IconButton>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5 type-body text-ink">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line-soft px-5 py-3">{footer}</div>}
      </div>
    </dialog>
  )
}
