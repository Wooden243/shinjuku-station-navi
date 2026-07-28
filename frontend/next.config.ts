import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const capacitorBuild = process.env.CAPACITOR_BUILD === "true";

const nextConfig: NextConfig = {
  output: capacitorBuild ? "export" : undefined,
  trailingSlash: capacitorBuild,
  poweredByHeader: false,
  async rewrites() {
    if (capacitorBuild) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  async headers() {
    if (capacitorBuild) return [];
    return [
      {
        source: "/sw.js",
        headers: [{ key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }],
      },
      {
        source: "/manifest.webmanifest",
        headers: [{ key: "Content-Type", value: "application/manifest+json" }],
      },
    ];
  },
};

export default nextConfig;
