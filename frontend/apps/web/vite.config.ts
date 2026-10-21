import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In Docker the API is reachable as http://api:8000; on the host it sits behind nginx.
const apiTarget = process.env.EMS_API_URL ?? "http://localhost:8080";

export default defineConfig({
  plugins: [tanstackRouter({ target: "react", autoCodeSplitting: true }), react(), tailwindcss()],
  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": { target: apiTarget, changeOrigin: false } },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], globals: false },
});
