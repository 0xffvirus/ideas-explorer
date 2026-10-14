import type { NextConfig } from "next";

// Mocking is a dev/e2e-only mode. Refuse to *production-build* a mock-enabled
// bundle unless the caller explicitly opts in (Playwright sets
// ALLOW_MOCK_BUILD=1), so a stray flag can never ship mock data as "prod".
if (
  process.env.NODE_ENV === "production" &&
  process.env.NEXT_PUBLIC_API_MOCKING === "enabled" &&
  process.env.ALLOW_MOCK_BUILD !== "1"
) {
  throw new Error(
    "Refusing to build with NEXT_PUBLIC_API_MOCKING=enabled. Set ALLOW_MOCK_BUILD=1 for e2e builds.",
  );
}

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  typedRoutes: true,
  // E2E builds go to a separate output dir so `pnpm start` can never serve a
  // mock-enabled artifact by accident.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
