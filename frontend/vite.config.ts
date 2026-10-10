/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

const backend = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

// Hosts allowed besides localhost: HTTPS tunnels for trying Leon on a phone, plus any listed in
// VITE_ALLOWED_HOSTS (comma-separated).
const allowedHosts = [
  ".trycloudflare.com",
  ".ngrok-free.app",
  ...(process.env.VITE_ALLOWED_HOSTS ?? "").split(",").filter(Boolean),
];

/** Proxy to Django, telling it which host the browser used (for its same-origin checks). */
const toBackend = {
  target: backend,
  changeOrigin: true,
  configure: (proxy: { on: (event: "proxyReq", handler: ProxyReqHandler) => void }) => {
    proxy.on("proxyReq", (proxyReq, req) => {
      if (req.headers.host) proxyReq.setHeader("X-Forwarded-Host", req.headers.host);
    });
  },
};
type ProxyReqHandler = (
  proxyReq: { setHeader: (name: string, value: string) => void },
  req: { headers: { host?: string } },
) => void;

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    host: true,
    port: 5173,
    allowedHosts,
    // Docker on Windows and macOS doesn't pass file-change events into the container.
    watch: process.env.VITE_POLL === "true" ? { usePolling: true, interval: 300 } : undefined,
    proxy: { "/api": toBackend, "/admin": toBackend, "/static": toBackend },
  },
  build: {
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (/node_modules\/(react|react-dom|react-router|react-router-dom|scheduler)\//.test(id))
            return "react";
          if (/node_modules\/(@tanstack|zustand|openapi-fetch)\//.test(id)) return "query";
          return undefined;
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
