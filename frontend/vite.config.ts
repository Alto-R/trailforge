import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: forward /api/* to the FastAPI backend so the browser sees a
// same-origin URL (avoids CORS fuss even though the backend allows it).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // e2e/ is driven by Playwright, not Vitest — keep it out of `vitest run`.
    exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**"],
  },
});
