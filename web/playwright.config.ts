import { defineConfig } from "@playwright/test";
import { config as loadEnv } from "dotenv";

loadEnv({ path: ".env.local", quiet: true });

export default defineConfig({
  testDir: "e2e",
  use: {
    baseURL: "http://localhost:3000",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: [
    {
      command: "uv run --env-file .env uvicorn api.main:app --port 8000",
      cwd: "../backend",
      url: "http://localhost:8000/healthz",
      reuseExistingServer: true,
    },
    {
      command: "pnpm dev",
      url: "http://localhost:3000/login",
      reuseExistingServer: true,
    },
  ],
});
