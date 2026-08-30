import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // Vite blocks requests with an unrecognized Host header by default (DNS-
    // rebinding protection — same class of check the MCP SDK does for its
    // own transport). Dev-only convenience for testing through a cloudflared/
    // ngrok tunnel; irrelevant in prod, where nginx serves a static build,
    // not this dev server.
    allowedHosts: ['.trycloudflare.com', '.ngrok-free.dev', '.ngrok-free.app'],
  },
})
