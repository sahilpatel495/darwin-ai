import { useEffect, useId, useRef } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import IconButton from './IconButton'
import { CloseIcon } from './icons'
import { cx } from './cx'

export interface DrawerProps {
  open: boolean
  /** Called for every way out: the close button, Esc, and a click on the scrim. */
  onClose: () => void
  /** Names the drawer and is rendered as its heading. Sentence case. */
  title: string
  /** One quiet line under the title. */
  description?: ReactNode
  children: ReactNode
  /** Controls pinned to the bottom edge, e.g. "Add files". */
  footer?: ReactNode
  className?: string
}

/**
 * The right slide-over (§5): 480px on a desktop, the whole screen on a phone. It is where the
 * Data panel lives now that there is no permanent side column.
 *
 * Built on the native <dialog>, which already traps focus, closes on Esc and hands focus back to
 * whatever opened it — the same machinery as Dialog, positioned against the right edge instead of
 * the middle. The base stylesheet's centred `dialog` rules are undone here in one place.
 */
export default function Drawer({ open, onClose, title, description, children, footer, className }: DrawerProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const el = ref.current
    if (!el) return
    // showModal() on an open dialog throws; close() on a closed one is a no-op. Guard both so a
    // re-render never breaks the drawer.
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])

  // A click on the scrim lands on the <dialog> element itself, never on the inner panel.
  const onScrimClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === ref.current) onClose()
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={onScrimClick}
      className={cx(
        // `mr-0` beats the base stylesheet's `margin: auto`, which is what centres a Dialog.
        'm-0 ml-auto h-dvh max-h-dvh w-full max-w-full rounded-none border-l border-hairline-soft',
        'shadow-level-2 sm:w-[480px] sm:rounded-l-xxl',
        className,
      )}
    >
      <div className="drawer-in flex h-full flex-col bg-canvas">
        <div className="flex shrink-0 items-start gap-4 border-b border-hairline-soft px-6 pt-6 pb-4">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-heading-sm text-ink-deep">
              {title}
            </h2>
            {description && <p className="mt-1 text-body-sm text-slate">{description}</p>}
          </div>
          <IconButton label="Close" variant="ghost" tooltipSide="bottom" onClick={onClose} className="-mt-1 -mr-2">
            <CloseIcon size={18} />
          </IconButton>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>

        {footer && <div className="shrink-0 border-t border-hairline-soft px-6 py-4">{footer}</div>}
      </div>
    </dialog>
  )
}
