import { resolve } from 'node:path';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
var appRoot = __dirname;
var workspaceRoot = resolve(appRoot, '..');
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(appRoot, 'src'),
    },
  },
  server: {
    fs: { allow: [workspaceRoot, appRoot] },
    port: 5173,
    open: true,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true, secure: false } },
  },
  test: {
    root: appRoot,
    globals: true,
    environment: 'jsdom',
    setupFiles: resolve(appRoot, 'src/test/setup.ts'),
    include: ['src/**/*.{test,spec}.{ts,tsx}', '../tests/**/*.{test,spec}.{ts,tsx}'],
    css: true,
    deps: {
      moduleDirectories: [resolve(appRoot, 'node_modules'), 'node_modules'],
    },
  },
});
