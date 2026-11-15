import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

const frontendDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendDir, '..');

function resolvePythonExecutable(): string {
  if (process.env.SAR2ACTION_PYTHON) return process.env.SAR2ACTION_PYTHON;
  const candidates = [
    resolve(repoRoot, '.venv', 'Scripts', 'python.exe'),
    resolve(repoRoot, '.venv', 'bin', 'python'),
    resolve(repoRoot, 'venv', 'Scripts', 'python.exe'),
    resolve(repoRoot, 'venv', 'bin', 'python'),
  ];
  return candidates.find((candidate) => existsSync(candidate)) ?? 'python';
}

const backendPort = process.env.SAR2ACTION_E2E_BACKEND_PORT || '18017';
const frontendPort = process.env.SAR2ACTION_E2E_FRONTEND_PORT || '15174';
const backendUrl = `http://127.0.0.1:${backendPort}`;
const managedServers = process.env.SAR2ACTION_GIS_E2E === '1';

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  use: {
    baseURL: process.env.SAR2ACTION_E2E_BASE_URL || (managedServers ? `http://127.0.0.1:${frontendPort}` : 'http://127.0.0.1:5173'),
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chrome', use: { ...devices['Desktop Chrome'], channel: 'chrome' } }],
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  ...(managedServers
    ? {
        webServer: [
          {
            command: `"${resolvePythonExecutable()}" -m uvicorn backend.app.main:app --host 127.0.0.1 --port ${backendPort}`,
            cwd: process.env.SAR2ACTION_BACKEND_CWD || repoRoot,
            url: `${backendUrl}/api/health`,
            reuseExistingServer: false,
            timeout: 60_000,
          },
          {
            command: `npx vite preview --host 127.0.0.1 --port ${frontendPort}`,
            cwd: frontendDir,
            env: { SAR2ACTION_BACKEND_URL: backendUrl },
            url: `http://127.0.0.1:${frontendPort}/`,
            reuseExistingServer: false,
            timeout: 60_000,
          },
        ],
      }
    : {}),
});
