import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The FastAPI server owns /api (JSON + live stream), /static (fonts, logos), /guide and /favicon.ico.
// In development Vite proxies those to it; in production FastAPI serves the build from web/dist.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.NOCTURNE_BACKEND_URL;
  const proxied = ["/api", "/static", "/guide", "/favicon.ico"];
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: Number(env.NOCTURNE_DEV_PORT) || undefined,
      proxy: backend ? Object.fromEntries(proxied.map((p) => [p, { target: backend, changeOrigin: false }])) : undefined,
    },
    build: { outDir: "../web/dist", emptyOutDir: true, sourcemap: false },
  };
});
