import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tsconfigPaths()], // ✅ Adds TypeScript path alias support
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE_URL || "http://localhost:7071", // ✅ Uses env variable
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
    headers: {
      "Cross-Origin-Opener-Policy": "unsafe-none",  // ✅ Keeps popups working
      "Cross-Origin-Embedder-Policy": "unsafe-none" // ✅ Allows external popups
    }
  }
});
