import type { NextConfig } from "next";

// The browser only ever talks to this app's origin. /api/v1/* is proxied to the FastAPI
// server, so the HTTP-only session cookie stays first-party and no CORS is needed.
const apiUrl = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Next's gzip holds back the progress stream (SSE) until it ends, so the student would see
  // no progress. Compress at the reverse proxy instead, excluding text/event-stream.
  compress: false,
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiUrl}/api/v1/:path*` }];
  },
  experimental: {
    // The progress stream sends a keep-alive every 15 s; allow long quiet gaps anyway.
    proxyTimeout: 120_000,
  },
};

export default nextConfig;
