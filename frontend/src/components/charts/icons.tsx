// The glyphs the answer card needs that the shared set does not carry. Same grid, same stroke,
// same rules as components/ui/icons.tsx: 20px box, 1.7px, currentColor, decorative — every one of
// them sits inside an IconButton whose `label` is the real name.

import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

const Icon = ({ size = 20, children, ...rest }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden {...rest}>
    {children}
  </svg>
)

export const ExpandIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3h5v5M17 3l-6 6M8 17H3v-5M3 17l6-6" />
  </Icon>
)

export const DownloadIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10 3v9m0 0 3.5-3.5M10 12 6.5 8.5" />
    <path d="M3.5 14v1.5A1.5 1.5 0 0 0 5 17h10a1.5 1.5 0 0 0 1.5-1.5V14" />
  </Icon>
)

// Two sheets, the front one offset: the answer's sentence, copied.
export const CopyIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="7" y="7" width="9.5" height="9.5" rx="2.2" />
    <path d="M13 4.5H5.7A1.2 1.2 0 0 0 4.5 5.7V13" />
  </Icon>
)

