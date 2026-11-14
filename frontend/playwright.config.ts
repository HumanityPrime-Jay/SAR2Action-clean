import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  use: { baseURL: process.env.SAR2ACTION_E2E_BASE_URL || 'http://127.0.0.1:5173', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chrome', use: { ...devices['Desktop Chrome'], channel: 'chrome' } }],
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  ...(process.env.SAR2ACTION_GIS_E2E === '1'
    ? {
        webServer: [
          {
            command: 'D:\\NASA\\SAR2Action\\.venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 18017',
            cwd: process.env.SAR2ACTION_BACKEND_CWD || 'D:\\NASA\\SAR2Action',
            url: 'http://127.0.0.1:18017/openapi.json',
            timeout: 60_000,
          },
          {
            command: 'npm run preview -- --host 127.0.0.1 --port 15174',
            cwd: 'D:\\NASA\\SAR2Action-clean-PR1-frontend\\frontend',
            env: { SAR2ACTION_BACKEND_URL: 'http://127.0.0.1:18017' },
            url: 'http://127.0.0.1:15174/',
            timeout: 60_000,
          },
        ],
      }
    : {}),
});
