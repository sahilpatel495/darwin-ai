// The product's glyphs. One outline set, 20px grid, 1.7px strokes, `currentColor`, so an icon
// takes the colour of whatever it sits in and never needs a second variant.
//
// Decorative by default: every icon in this app sits beside its own words, or inside a control
// that carries them in `aria-label`. Hence aria-hidden on all of them.

import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Icon({ size = 20, children, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...rest}
    >
      {children}
    </svg>
  )
}

/* --- The six places you can go (§6 v2) ----------------------------------- */
export const HomeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3.5 8.5 10 3l6.5 5.5" />
    <path d="M5 8.2V16a.5.5 0 0 0 .5.5H8V12h4v4.5h2.5a.5.5 0 0 0 .5-.5V8.2" />
  </Icon>
)
export const AskIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M17 11.5a2 2 0 0 1-2 2h-3.5L7 17v-3.5H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2Z" />
    <path d="M7.5 7.5h5M7.5 10.5h3" />
  </Icon>
)
export const OverviewIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="2.75" y="2.75" width="6" height="6" rx="1.4" />
    <rect x="11.25" y="2.75" width="6" height="6" rx="1.4" />
    <rect x="2.75" y="11.25" width="6" height="6" rx="1.4" />
    <rect x="11.25" y="11.25" width="6" height="6" rx="1.4" />
  </Icon>
)
export const AnalysesIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 16.5h14" />
    <path d="M5.5 13v-3M9 13V5.5M12.5 13v-5M16 13V8" />
  </Icon>
)
export const SavedIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5.5 3h9a.5.5 0 0 1 .5.5v13.1a.4.4 0 0 1-.63.33L10 13.8l-4.37 3.13A.4.4 0 0 1 5 16.6V3.5a.5.5 0 0 1 .5-.5Z" />
  </Icon>
)
export const TrustIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10 2.75 16 5v4.6c0 3.4-2.4 6.4-6 7.65-3.6-1.25-6-4.25-6-7.65V5Z" />
    <path d="m7.4 9.9 1.9 1.9 3.4-3.6" />
  </Icon>
)

/* --- Controls ------------------------------------------------------------ */
export const CheckIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m4.5 10.4 3.4 3.4 7.6-7.8" />
  </Icon>
)
export const CloseIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 5l10 10M15 5 5 15" />
  </Icon>
)
export const ChevronIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m7.5 4.5 6 5.5-6 5.5" />
  </Icon>
)
export const MoreIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="4.5" cy="10" r="1.1" fill="currentColor" stroke="none" />
    <circle cx="10" cy="10" r="1.1" fill="currentColor" stroke="none" />
    <circle cx="15.5" cy="10" r="1.1" fill="currentColor" stroke="none" />
  </Icon>
)
/* --- The top bar (§6) ---------------------------------------------------- */
export const SearchIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="9" cy="9" r="5.25" />
    <path d="m12.9 12.9 3.6 3.6" />
  </Icon>
)
export const DataIcon = (p: IconProps) => (
  <Icon {...p}>
    <ellipse cx="10" cy="5.25" rx="6" ry="2.5" />
    <path d="M4 5.25V14.75c0 1.38 2.69 2.5 6 2.5s6-1.12 6-2.5V5.25" />
    <path d="M4 10c0 1.38 2.69 2.5 6 2.5s6-1.12 6-2.5" />
  </Icon>
)
export const PlusIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10 4.5v11M4.5 10h11" />
  </Icon>
)
export const ArrowUpIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10 16V4.5M10 4.5 5.5 9M10 4.5 14.5 9" />
  </Icon>
)
