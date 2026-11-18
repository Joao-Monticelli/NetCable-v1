import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// NETCABLE_API_PROXY e NETCABLE_DEV_PORT permitem rodar uma segunda instância
// (ex.: o robô de QA em qa/) ao lado do ambiente de desenvolvimento normal.
const API = process.env.NETCABLE_API_PROXY || 'http://127.0.0.1:8000'
const PORTA = Number(process.env.NETCABLE_DEV_PORT || 5173)

export default defineConfig({
  plugins: [react()],
  // Cache separado por porta, para duas instâncias não disputarem o mesmo cache.
  cacheDir: PORTA === 5173 ? 'node_modules/.vite' : `node_modules/.vite-${PORTA}`,
  server: {
    host: '0.0.0.0', // Permite acesso por IP na rede local
    port: PORTA,
    strictPort: true,
    proxy: {
      '/api': {
        target: API,
        changeOrigin: true,
      },
    },
  }
})
