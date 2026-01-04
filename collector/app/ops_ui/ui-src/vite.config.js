const path = require("path");
const { defineConfig } = require("vite");

module.exports = defineConfig({
  base: "/dashboard/ui/static/ui/dist/",
  build: {
    outDir: path.resolve(__dirname, "../static/ui/dist"),
    emptyOutDir: true,
    manifest: "manifest.json",
    rollupOptions: {
      input: path.resolve(__dirname, "main.js"),
      output: {
        entryFileNames: "assets/[name].[hash].js",
        chunkFileNames: "assets/[name].[hash].js",
        assetFileNames: "assets/[name].[hash].[ext]",
      },
    },
  },
});
