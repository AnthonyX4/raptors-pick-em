import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// the browser only ever talks to this origin: the dev server forwards /api and /static to fastapi,
// and nginx does the same in production, so there is no cors and no api url to configure.
// ws: true lets the chat's websocket (/api/games/<id>/ws) through the /api entry as well
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  test: {
    environment: 'node', // the logic under test needs fetch and localStorage, which the tests stub
    include: ['src/**/*.test.ts'],
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', ws: true },
      '/static': 'http://localhost:8000',
    },
  },
})
