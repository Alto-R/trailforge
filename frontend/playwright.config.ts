import { defineConfig, devices } from "@playwright/test";

// Smoke E2E for the TrailForge demo.
//
// Requires the FastAPI backend already running on :8000 — the Vite dev server
// (started below) proxies /api/* to it. Run the backend first, then `npm run e2e`.
// First run also needs the browser binary: `npx playwright install chromium`.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000, // headless WebGL (deck.gl) + map load needs headroom
  fullyParallel: false,
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      // taller than 720 so the control panel + first candidate card both fit
      use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 1000 } },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
