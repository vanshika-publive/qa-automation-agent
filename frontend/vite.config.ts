import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Overridden to the Docker Compose service name ('http://backend:8000') when
// running in a container; defaults to localhost for native dev.
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '/reports': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
