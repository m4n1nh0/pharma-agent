import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Em dev, o Vite roda em :5173 e faz proxy das rotas da API para o FastAPI em :8000.
// Em produção, o build (dist/) é servido pelo próprio FastAPI (ver src/presentation/api/app.py).
// "127.0.0.1" em vez de "localhost": no Windows o Node resolve "localhost" para ::1 (IPv6)
// primeiro, e o backend (uvicorn em 0.0.0.0) não escuta em ::1 — proxy falha com ECONNREFUSED.
const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000";
const API_PATHS = ["/auth", "/analyze", "/interactions", "/prescription-review", "/stream-analysis", "/jobs", "/health", "/metrics"];

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_PATHS.map((p) => [p, { target: API_TARGET, changeOrigin: true }])
    ),
  },
  build: {
    outDir: "dist",
  },
});
