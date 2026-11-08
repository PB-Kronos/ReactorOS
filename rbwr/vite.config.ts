import { defineConfig } from "vite";
import dyadComponentTagger from "@dyad-sh/react-vite-component-tagger";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { cpSync } from "node:fs";

export default defineConfig(({ command }) => ({
  publicDir: command === "build" ? false : "public",
  server: {
    host: "::",
    port: 1080,
    allowedHosts: true,
  },
  plugins: [dyadComponentTagger(), react(), {
    name: "reactoros-public-assets",
    apply: "build",
    writeBundle(options) {
      const publicRoot = path.resolve(__dirname, "public");
      const excluded = new Set(["audio", "hes-archive-favicon.svg"]);
      cpSync(publicRoot, options.dir!, {
        recursive: true,
        filter: source => !excluded.has(path.relative(publicRoot, source).split(path.sep)[0]),
      });
    },
  }],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
