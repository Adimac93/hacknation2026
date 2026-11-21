import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 150_000 },
  reporter: "list",
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080" },
});
