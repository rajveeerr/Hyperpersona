import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react-swc";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    /** Framer Motion must share the same React as the app or hooks throw `resolveDispatcher().useState`. */
    dedupe: ["react", "react-dom"],
  },
  /**
   * When `VITE_USE_MOCKS=false`, the MSW worker stops intercepting most routes
   * and the FE talks to the real FastAPI backend. The BE has no `/api` prefix,
   * so we proxy `/api/*` → `<VITE_BACKEND_URL>/*` here. When MSW is on, the SW
   * intercepts before this proxy ever sees the request.
   */
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
});
