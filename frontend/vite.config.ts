import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/recharts')) return 'charts';
          if (id.includes('node_modules/leaflet') || id.includes('node_modules/react-leaflet')) return 'leaflet';
          if (id.includes('node_modules/lucide-react')) return 'icons';
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom') || id.includes('node_modules/react-router')) return 'vendor';
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
})

