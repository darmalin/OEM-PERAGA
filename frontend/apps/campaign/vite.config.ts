import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// On the host the API sits behind nginx at :8080 (compose); in Docker it is http://api:8000.
const apiTarget = process.env.EMS_API_URL ?? "http://localhost:8080";

export default defineConfig({
  // Public campaign forms, served next to the desk app at /r/{token} (frontend/Dockerfile).
  base: "/r/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
  server: {
    host: true,
    port: 5175,
    proxy: { "/api": { target: apiTarget, changeOrigin: false } },
  },
  test: { environment: "jsdom", globals: false },
});
