// Light, dark or follow the system, remembered in this browser (§5).
//
// <html data-theme> is the single switch: index.css redefines every colour token under
// [data-theme="dark"], so nothing in the app ever branches on the theme. The first stamp
// happens in the inline script in index.html, before React loads, so a dark-mode reload
// never flashes white — keep the key and the values here in step with that script.

import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark' | 'system'

const KEY = 'verity.theme'
const DARK = '(prefers-color-scheme: dark)'

/** What the browser remembers. Storage can be switched off, so never assume it answers. */
export function getTheme(): Theme {
  try {
    const stored = localStorage.getItem(KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  } catch {
    /* private mode */
  }
  return 'system'
}

/** The theme a choice of `system` actually resolves to right now. */
export const resolveTheme = (theme: Theme): 'light' | 'dark' =>
  theme === 'system' ? (matchMedia(DARK).matches ? 'dark' : 'light') : theme

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = resolveTheme(theme)
  try {
    // `system` is stored as an absence, so a browser that later changes its mind is followed.
    if (theme === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, theme)
  } catch {
    /* private mode: the theme still applies for this visit */
  }
}

/** The choice, plus a setter. While the choice is `system`, an OS switch lands immediately. */
export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, set] = useState<Theme>(getTheme)

  useEffect(() => {
    setTheme(theme)
    if (theme !== 'system') return
    const media = matchMedia(DARK)
    const follow = () => setTheme('system')
    media.addEventListener('change', follow)
    return () => media.removeEventListener('change', follow)
  }, [theme])

  return [theme, set]
}
