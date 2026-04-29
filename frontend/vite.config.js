import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health':      { target: 'http://localhost:3001', changeOrigin: true },
      '/devices':     { target: 'http://localhost:3001', changeOrigin: true },
      '/readings':    { target: 'http://localhost:3001', changeOrigin: true },
      '/livemonitor': { target: 'http://localhost:3001', changeOrigin: true },
      '/socket.io':   { target: 'http://localhost:3001', changeOrigin: true, ws: true },
    }
  }
});
