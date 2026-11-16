import { fileURLToPath, URL } from "node:url"
import type { ServerResponse } from "node:http"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, type ProxyOptions } from "vite"

const srcDir = fileURLToPath(new URL("./src", import.meta.url))
const API_TARGET = "http://127.0.0.1:5055"

function careLoopProxy(): ProxyOptions {
  return {
    target: API_TARGET,
    changeOrigin: true,
    timeout: 25000,
    configure(proxy) {
      proxy.on("error", (_error, _req, res) => {
        if (!res || typeof res !== "object" || !("writeHead" in res)) return
        const response = res as ServerResponse
        if (response.headersSent || response.writableEnded) return
        const message = `The CareLoop API is not running. The dev proxy targets ${API_TARGET}.`
        response.writeHead(502, { "Content-Type": "application/json" })
        response.end(JSON.stringify({ error: { code: "bad_gateway", message, details: [] } }))
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": srcDir,
    },
  },
  server: {
    proxy: {
      "/api": careLoopProxy(),
    },
  },
  preview: {
    proxy: {
      "/api": careLoopProxy(),
    },
  },
})
