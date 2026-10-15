import type { NextConfig } from "next";

const apiInternalUrl =
  process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Same-origin /api → FastAPI (docs/architecture.md request flow).
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiInternalUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
