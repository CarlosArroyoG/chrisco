import { defineConfig } from '@playwright/test';
import { API_PORT, BACKEND_ENV, WEB_PORT, WEB_URL } from './env';

export default defineConfig({
  testDir: './tests',
  globalSetup: './global-setup.ts',
  // El recorrido es una historia continua (registro → revisión → equipo): no se paraleliza.
  workers: 1,
  fullyParallel: false,
  timeout: 60_000,
  reporter: [['list']],
  use: {
    baseURL: WEB_URL,
    trace: 'retain-on-failure',
    // En local se usa el Edge instalado (E2E_CHANNEL=msedge); en CI, el Chromium de Playwright.
    channel: process.env['E2E_CHANNEL'] || undefined,
  },
  webServer: [
    {
      command: `uv run uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: '../backend',
      env: BACKEND_ENV,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx ng serve --port ${WEB_PORT} --proxy-config ../e2e/proxy.e2e.json`,
      cwd: '../frontend',
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
