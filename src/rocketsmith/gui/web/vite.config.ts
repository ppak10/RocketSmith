import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/**
 * Strip `type="module"` and `crossorigin` from built script/link tags so the
 * bundle loads over file:// (browsers block ES modules on that protocol).
 */
function fileProtocolCompat() {
  return {
    name: "file-protocol-compat",
    apply: "build" as const,
    transformIndexHtml(html: string) {
      return html
        .replace(/ type="module"/g, " defer")
        .replace(/ crossorigin/g, "")
        .replace(
          "<script defer",
          '<script defer src="./offline-data.js"></script>\n    <script defer',
        );
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), fileProtocolCompat()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  base: "./",
  build: {
    outDir: "../../data/gui",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        format: "iife",
        entryFileNames: "main.js",
        assetFileNames: "[name][extname]",
        chunkFileNames: "[name].js",
        inlineDynamicImports: true,
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
