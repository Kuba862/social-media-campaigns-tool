import { defineConfig } from "@playwright/test";
import { config as loadEnv } from "dotenv";

loadEnv({ path: ".env.local", quiet: true });

/** Where the tests point; a second checkout can run on spare ports without touching the first. */
const WEB = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const port = (url: string): string => new URL(url).port;

export default defineConfig({
  testDir: "e2e",
  use: {
    baseURL: WEB,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: [
    {
      command: `uv run --env-file .env uvicorn api.main:app --port ${port(API)}`,
      cwd: "../backend",
      url: `${API}/healthz`,
      reuseExistingServer: true,
    },
    {
      command: `pnpm dev --port ${port(WEB)}`,
      url: `${WEB}/login`,
      reuseExistingServer: true,
    },
  ],
});
