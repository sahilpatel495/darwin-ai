// The four icons the shell needs, inline so there is no icon dependency. All are decorative:
// every control that uses one also has a text label, so they are hidden from screen readers.

const base = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
  className: 'shrink-0',
} as const

export const ShieldIcon = () => (
  <svg {...base}>
    <path d="M12 3l8 3v6c0 4.5-3.2 8.2-8 9-4.8-.8-8-4.5-8-9V6l8-3z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
)

export const UploadIcon = () => (
  <svg {...base} width={28} height={28} strokeWidth={1.5}>
    <path d="M12 16V4" />
    <path d="M7 9l5-5 5 5" />
    <path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" />
  </svg>
)

export const CheckIcon = () => (
  <svg {...base} width={14} height={14} strokeWidth={2.5}>
    <path d="M5 12l5 5 9-10" />
  </svg>
)

export const AlertIcon = () => (
  <svg {...base} width={14} height={14} strokeWidth={2.5}>
    <path d="M12 4v10" />
    <path d="M12 19v.5" />
  </svg>
)
