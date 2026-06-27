import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El backend FastAPI sigue en 127.0.0.1:8077; el dev server proxya /api hacia allí.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8077' },
    // X: es una unidad virtual/de red: fs.watch nativo falla (UNKNOWN watch) -> polling
    watch: { usePolling: true, interval: 300 },
  },
})
