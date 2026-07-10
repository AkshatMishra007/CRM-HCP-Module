import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite config - plain React, no extra plugins needed
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
})
