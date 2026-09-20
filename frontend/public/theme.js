// Theme before first paint, so a dark-mode reload never flashes white.
//
// A file rather than an inline <script> on purpose: the server sends
// `Content-Security-Policy: default-src 'self'` with no script-src, so an inline script is
// refused in production and every reload would flash the light theme. Touches no network, and
// mirrors src/components/ui/theme.ts — keep the key and the values in step with that file.
;(function () {
  try {
    var stored = localStorage.getItem('verity.theme')
    var choice = stored === 'light' || stored === 'dark' ? stored : null
    var dark = choice ? choice === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  } catch (e) {
    /* Private mode blocks storage; the light default in the markup already stands. */
  }
})()
