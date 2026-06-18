// import { defineConfig, loadEnv } from "vite";
// import react from "@vitejs/plugin-react";
// import path from "path";

// // ---------------------------------------------------------------------------
// // Vite configuration
// //
// // Proxy: all /api requests forwarded to the FastAPI backend.
// // The proxy target adapts to the runtime environment:
// //   - Inside Docker Compose: target = http://backend:8000  (internal DNS)
// //   - Outside Docker (local npm run dev): target = http://localhost:8000
// //
// // This is controlled by the VITE_BACKEND_URL env variable.
// // docker-compose.yml sets it to http://backend:8000.
// // When unset (local dev), it defaults to http://localhost:8000.
// //
// // Test: vitest with jsdom, React Testing Library, and MSW.
// // ---------------------------------------------------------------------------

// export default defineConfig(({ mode }) => {
//   // Load env so we can read VITE_BACKEND_URL at config time
//   const env = loadEnv(mode, process.cwd(), "");
//   const backendUrl = env.VITE_BACKEND_URL ?? "http://localhost:8000";

//   return {
//     plugins: [react()],

//     // ── Path aliases ─────────────────────────────────────────────────────────
//     // @/ maps to src/ — consistent with tsconfig.json paths.
//     resolve: {
//       alias: {
//         "@": path.resolve(__dirname, "./src"),
//       },
//     },

//     // ── Dev server ───────────────────────────────────────────────────────────
//     server: {
//       port: 5173,
//       host: true, // Required for Docker networking (0.0.0.0)
//       proxy: {
//         // All /api/* requests are forwarded to the FastAPI backend.
//         // changeOrigin rewrites the Host header so the backend's CORS
//         // middleware sees the correct origin.
//         "/api": {
//           target: backendUrl,
//           changeOrigin: true,
//           secure: false,
//         },
//       },
//     },

//     // ── Build ────────────────────────────────────────────────────────────────
//     build: {
//       outDir: "dist",
//       sourcemap: true,
//       rollupOptions: {
//         output: {
//           manualChunks: {
//             // Vendor chunk split — keeps main bundle lean
//             vendor: ["react", "react-dom", "react-router-dom"],
//             charts: ["recharts"],
//             query: ["@tanstack/react-query"],
//           },
//         },
//       },
//     },

//     // ── Test (Vitest) ────────────────────────────────────────────────────────
//     test: {
//       globals: true,
//       environment: "jsdom",
//       setupFiles: ["./tests/setup.ts"],

//       // Resolve @/ aliases in tests
//       alias: {
//         "@": path.resolve(__dirname, "./src"),
//       },

//       // Inject env variables for tests — bypasses Keycloak OAuth flow
//       // so AuthContext returns the dev mock user (AUDITOR, tenant: demo).
//       env: {
//         VITE_SKIP_AUTH: "true",
//         VITE_PLATFORM_DOMAIN: "platform.local",
//         VITE_KEYCLOAK_URL: "http://localhost:8080",
//         VITE_KEYCLOAK_REALM: "audit-platform",
//         VITE_KEYCLOAK_CLIENT_ID: "audit-platform-frontend",
//         VITE_BACKEND_URL: "http://localhost:8000",
//       },

//       coverage: {
//         provider: "v8",
//         reporter: ["text", "html", "lcov"],
//         include: [
//           "src/components/**",
//           "src/features/**",
//           "src/hooks/**",
//           "src/utils/**",
//         ],
//         thresholds: {
//           lines: 75,
//           functions: 75,
//           branches: 70,
//           statements: 75,
//         },
//       },
//     },
//   };
// });


import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// ---------------------------------------------------------------------------
// Vite configuration
//
// Proxy: all /api requests forwarded to the FastAPI backend.
// The proxy target adapts to the runtime environment:
//   - Inside Docker Compose: target = http://backend:8000  (internal DNS)
//   - Outside Docker (local npm run dev): target = http://localhost:8000
//
// This is controlled by the VITE_BACKEND_URL env variable.
// docker-compose.yml sets it to http://backend:8000.
// When unset (local dev), it defaults to http://localhost:8000.
//
// Test: vitest with jsdom, React Testing Library, and MSW.
// ---------------------------------------------------------------------------

export default defineConfig(({ mode }) => {
  // Load env so we can read VITE_BACKEND_URL at config time
  const env = loadEnv(mode, process.cwd(), "");
  const backendUrl = env.VITE_BACKEND_URL ?? "http://localhost:8000";

  return {
    plugins: [react()],

    // ── Path aliases ─────────────────────────────────────────────────────────
    // @/ maps to src/ — consistent with tsconfig.json paths.
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },

    // ── Dev server ───────────────────────────────────────────────────────────
    server: {
      port: 5173,
      host: true, // Required for Docker networking (0.0.0.0)
      proxy: {
        // /api/* — tenant-scoped API endpoints
        "/api": {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
        // /platform/* — SUPER_ADMIN platform endpoints
        // These are NOT prefixed with /api in the backend router, so they
        // need their own proxy rule. Without this, POST /platform/tenants
        // hits the Vite dev server and returns 404.
        "/platform": {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
      },
    },

    // ── Build ────────────────────────────────────────────────────────────────
    build: {
      outDir: "dist",
      sourcemap: true,
      rollupOptions: {
        output: {
          manualChunks: {
            // Vendor chunk split — keeps main bundle lean
            vendor: ["react", "react-dom", "react-router-dom"],
            charts: ["recharts"],
            query: ["@tanstack/react-query"],
          },
        },
      },
    },

    // ── Test (Vitest) ────────────────────────────────────────────────────────
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./tests/setup.ts"],

      // Resolve @/ aliases in tests
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },

      // Inject env variables for tests — bypasses Keycloak OAuth flow
      // so AuthContext returns the dev mock user (AUDITOR, tenant: demo).
      env: {
        VITE_SKIP_AUTH: "true",
        VITE_PLATFORM_DOMAIN: "platform.local",
        VITE_KEYCLOAK_URL: "http://localhost:8080",
        VITE_KEYCLOAK_REALM: "audit-platform",
        VITE_KEYCLOAK_CLIENT_ID: "audit-platform-frontend",
        VITE_BACKEND_URL: "http://localhost:8000",
      },

      coverage: {
        provider: "v8",
        reporter: ["text", "html", "lcov"],
        include: [
          "src/components/**",
          "src/features/**",
          "src/hooks/**",
          "src/utils/**",
        ],
        thresholds: {
          lines: 75,
          functions: 75,
          branches: 70,
          statements: 75,
        },
      },
    },
  };
});