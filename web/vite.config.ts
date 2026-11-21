import { defineConfig } from "vitest/config";

// JSX is compiled by Vite's built-in esbuild (automatic runtime). We skip
// @vitejs/plugin-react on purpose: it pulls Babel -> browserslist -> caniuse-lite
// (CC-BY-4.0), which is outside the project's licence allow-list.
export default defineConfig({
  esbuild: { jsx: "automatic" },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "happy-dom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
