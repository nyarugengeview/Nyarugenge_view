import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', pool: 'forks', maxWorkers: 1, minWorkers: 1 } });
