import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "main.js",
        assetFileNames: "[name][extname]",
        chunkFileNames: "[name].js",
      },
    },
  },
  server: {
    proxy: {
      "/ws": {
        target: "ws://127.0.0.1:24881",
        ws: true,
      },
      "/api": {
        target: "http://127.0.0.1:24881",
      },
    },
  },
});
