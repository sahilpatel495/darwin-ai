import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev: Vite proxies /api to the API. Prod: FastAPI serves dist/.
// VITE_API_TARGET points the proxy elsewhere — a second checkout on another port, a colleague's
// machine — so two people can run the UI against one backend without editing this file.
const target = process.env.VITE_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': target } },
})
