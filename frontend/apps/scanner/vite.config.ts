import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

// In Docker the API is reachable as http://api:8000; on the host it sits behind nginx.
const apiTarget = process.env.EMS_API_URL ?? "http://localhost:8080";

export default defineConfig({
  // Served next to the desk app, at /scanner/ (frontend/Dockerfile).
  base: "/scanner/",
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: false,
      manifest: {
        name: "EMS Gate Scanner",
        short_name: "Gate Scanner",
        start_url: "/scanner/",
        scope: "/scanner/",
        display: "standalone",
        orientation: "portrait",
        background_color: "#171717",
        theme_color: "#171717",
        // No icons until the owner supplies a logo (known gap W3).
        icons: [],
      },
      workbox: {
        // App shell only. API responses are never cached here: scan data lives in IndexedDB.
        globPatterns: ["**/*.{js,css,html,woff2}"],
        navigateFallback: "/scanner/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
  server: {
    host: true,
    port: 5174,
    proxy: { "/api": { target: apiTarget, changeOrigin: false } },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], globals: false },
});
