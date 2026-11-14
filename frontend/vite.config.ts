import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  cacheDir: './.vite-cache',
  // MapLibre's worker is an ES module (`new Worker(url, { type: 'module' })`).
  worker: { format: 'es' },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.SAR2ACTION_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.ts'],
  },
});
