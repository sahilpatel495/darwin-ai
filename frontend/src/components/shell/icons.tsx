// The one icon the app draws itself, inline so there is no icon dependency. It is decorative: the
// control that uses it also has a text label, so it is hidden from screen readers. (Ticks are the
// Tick primitive, which is animated and is the ledger's own mark.)

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
