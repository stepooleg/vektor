/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

// Vite-конфигурация Vektor (AGENTS.md §4).
// Dev-сервер: http://localhost:5173, прокси /api → backend (по умолчанию :8000).
export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/node_modules/recharts/") || id.includes("/node_modules/d3-")) {
            return "vendor-charts";
          }
          if (id.includes("/node_modules/@ant-design/icons")) {
            return "vendor-icons";
          }
          if (id.includes("/node_modules/@ant-design/cssinjs")) {
            return "vendor-rc";
          }
          if (id.includes("/node_modules/rc-")) {
            return "vendor-rc";
          }
          if (
            id.includes("/node_modules/react/") ||
            id.includes("/node_modules/react-dom/") ||
            id.includes("/node_modules/react-router")
          ) {
            return "vendor-react";
          }
          if (id.includes("/node_modules/axios/")) {
            return "vendor-http";
          }
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    // Чистый вывод в CI; локально — через `npm run test:watch`.
    reporters: process.env.CI ? ["default"] : ["default"],
  },
});
