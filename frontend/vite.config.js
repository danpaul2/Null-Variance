import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  // frontEnd.JSX uses an uppercase extension, which Vite's default JSX
  // filters (and esbuild's loader map) don't match, so it gets served raw.
  // Both settings below teach the pipeline to treat *.JSX as JSX.
  plugins: [react({ include: /\.(jsx|JSX|js)$/ })],
  esbuild: { include: /\.(jsx|JSX|js|ts|tsx)$/, loader: "jsx" },
  optimizeDeps: {
    esbuildOptions: { loader: { ".JSX": "jsx", ".js": "jsx" } },
  },
  server: {
    open: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
