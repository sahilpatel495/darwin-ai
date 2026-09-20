// The two glyphs the shell needs and the primitives do not have. Same drawing as
// components/ui/icons.tsx — 20px grid, 1.7px strokes, currentColor — so they sit beside the
// nav rail's icons without looking borrowed. Decorative: every control that uses one also
// carries the words.

import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Icon({ size = 20, children, ...rest }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden {...rest}>
      {children}
    </svg>
  )
}

/** "How Verity works": a closed padlock, because the promise there is that nothing leaves. */
export const LockIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="4" y="8.5" width="12" height="8.5" rx="1.6" />
    <path d="M7 8.5V6.2a3 3 0 0 1 6 0v2.3" />
  </Icon>
)

/** "Data": a sheet with a header row, which is what the panel behind the button holds. */
export const DataIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="2.75" y="3.75" width="14.5" height="12.5" rx="1.6" />
    <path d="M2.75 7.75h14.5M8 7.75v8.5" />
  </Icon>
)
