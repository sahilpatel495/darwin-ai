import { cx } from './cx'

export interface AvatarProps {
  /** The person's name. Its initials are drawn, and it is the accessible name. */
  name: string
  /** A guest has no account yet, and the ring says so without a second label beside it. */
  guest?: boolean
  /** `md` 40px, the top bar · `sm` 32px, a list row · `lg` 64px, the profile page. */
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZE = { sm: 'size-8 text-caption', md: 'size-10 text-body-sm', lg: 'size-16 text-subtitle-lg' } as const

/** Two initials from "Sahil Patel" → "SP". A name is never blank here. */
const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('') || '?'

/**
 * A person, as two letters in a circle. No uploaded photos anywhere in the product, so there is no
 * image case to fall back from.
 */
export default function Avatar({ name, guest = false, size = 'md', className }: AvatarProps) {
  return (
    <span
      role="img"
      aria-label={guest ? `${name}, signed in as a guest` : name}
      className={cx(
        'inline-flex shrink-0 items-center justify-center rounded-circle font-bold',
        // A guest is the same circle in a quieter fill. It was a dashed outline, which at 40px in
        // the top bar reads as an empty slot waiting for something rather than as a person.
        guest ? 'bg-surface-soft text-charcoal ring-1 ring-hairline-soft ring-inset' : 'bg-ink-deep text-white',
        SIZE[size],
        className,
      )}
    >
      <span aria-hidden>{initials(name)}</span>
    </span>
  )
}
