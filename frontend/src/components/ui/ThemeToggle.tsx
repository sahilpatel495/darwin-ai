import IconButton from './IconButton'
import SegmentedControl from './SegmentedControl'
import { MoonIcon, SunIcon, SystemIcon } from './icons'
import { useTheme } from './theme'
import type { Theme } from './theme'

export interface ThemeToggleProps {
  /** `icon` one button that cycles — for the 72px nav rail · `full` the three named options. */
  variant?: 'icon' | 'full'
  className?: string
}

const OPTIONS = [
  { value: 'light', name: 'Light', icon: <SunIcon size={16} /> },
  { value: 'dark', name: 'Dark', icon: <MoonIcon size={16} /> },
  { value: 'system', name: 'Match my system', icon: <SystemIcon size={16} /> },
] as const

/** Light, dark, or whatever the device is set to. Remembered in this browser (§5). */
export default function ThemeToggle({ variant = 'icon', className }: ThemeToggleProps) {
  const [theme, setTheme] = useTheme()
  const here = OPTIONS.findIndex((option) => option.value === theme)
  const next = OPTIONS[(here + 1) % OPTIONS.length]

  // In the rail there is room for one 36px button, so it cycles. The label names where it goes,
  // not where it is, because that is what pressing it will do.
  if (variant === 'icon') {
    return (
      <IconButton label={`Appearance: ${OPTIONS[here].name.toLowerCase()}. Switch to ${next.name.toLowerCase()}.`} variant="ghost" className={className} onClick={() => setTheme(next.value as Theme)}>
        {OPTIONS[here].icon}
      </IconButton>
    )
  }

  return (
    <SegmentedControl
      label="Appearance"
      className={className}
      value={theme}
      onChange={(value) => setTheme(value as Theme)}
      options={OPTIONS.map((option) => ({
        value: option.value,
        name: option.name,
        label: (
          <>
            {option.icon}
            {option.name}
          </>
        ),
      }))}
    />
  )
}
