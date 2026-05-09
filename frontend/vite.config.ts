import path from "path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "tailwindcss";
import autoprefixer from "autoprefixer";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const isProd = mode === "production";

  // Refuse to produce a prod build that silently falls back to a localhost
  // backend — any deploy without VITE_API_URL set is a config bug we want
  // surfaced loudly at build time, not at runtime.
  if (isProd && !env.VITE_API_URL) {
    console.warn(
      "[vite] VITE_API_URL is not set for the production build. " +
        "Same-origin requests assume a reverse proxy in front of the API.",
    );
  }

  return {
    css: {
      postcss: {
        plugins: [tailwindcss, autoprefixer],
      },
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    // Strip all console.* and debugger statements from the production bundle
    // so caught errors don't leak stack traces / API payloads to the browser
    // console of end users.
    esbuild: {
      drop: isProd ? ["console", "debugger"] : [],
    },
    server: {
      // Only /api/* is forwarded to the backend; /docs and /openapi.json are
      // intentionally NOT proxied. The backend gates them on DBMANAGER_ENV
      // anyway, but stripping them here keeps the dev frontend honest with
      // the prod nginx config (which also doesn't expose them).
      proxy: {
        "/api": {
          target: env.VITE_API_URL || "http://localhost:8000",
          changeOrigin: true,
        },
      },
      host: true, // Needed for Docker
    },
  };
});
