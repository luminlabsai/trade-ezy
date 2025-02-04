import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:7071", // Backend URL
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
    headers: {
      "Cross-Origin-Opener-Policy": "unsafe-none",  // Loosens restrictions for popups
      "Cross-Origin-Embedder-Policy": "unsafe-none" // Allows external popups to work
    }
  }
});
