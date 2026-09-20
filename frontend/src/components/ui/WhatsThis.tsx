import Popover from './Popover'
import { cx } from './cx'

export interface WhatsThisProps {
  /** Heading inside the panel, e.g. "Why links matter". */
  title: string
  /** Two sentences at most (§5). The copy lives in components/education/explain.ts. */
  body: string
  align?: 'left' | 'right'
  className?: string
}

/**
 * The "?" beside anything the analyst has not met before: confidence, cross-check, an
 * agreed definition, Data Health, links, combined views, the clarify question.
 * It asks nothing of the reader — the interface still works if it is never opened.
 */
export default function WhatsThis({ title, body, align = 'left', className }: WhatsThisProps) {
  return (
    <Popover
      trigger="?"
      triggerLabel={`What's this? ${title}`}
      title={title}
      align={align}
      className={cx(
        'inline-flex size-[18px] items-center justify-center rounded-chip border border-rule-strong',
        'align-middle text-[11px] leading-none font-semibold text-ink-soft hover:bg-wash hover:text-ink',
        className,
      )}
    >
      {body}
    </Popover>
  )
}
