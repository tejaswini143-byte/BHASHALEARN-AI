import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "BHASHALEARN_");
  const apiTarget = env.BHASHALEARN_API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("/node_modules/three/")) return "vendor-three";
            if (id.includes("/node_modules/@react-three/")) return "vendor-react-three";
          },
        },
      },
    },
    server: {
      port: 5173,
      proxy: { "/api": apiTarget, "/health": apiTarget },
    },
  };
});
