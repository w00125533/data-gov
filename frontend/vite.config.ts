import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const governanceProxyTarget = process.env.VITE_GOVERNANCE_PROXY_TARGET ?? 'http://localhost:8080'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/rest': governanceProxyTarget,
    },
  },
})
