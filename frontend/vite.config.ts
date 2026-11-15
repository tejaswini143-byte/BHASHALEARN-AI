import { defineConfig } from 'vitest/config';
export default defineConfig({ server: { port: 5174 }, esbuild: { jsx: 'automatic' }, test: { include: ['src/**/*.test.tsx'], environment: 'jsdom', restoreMocks: true } });
