import type { NextConfig } from "next";

const isProduction = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  output: isProduction ? "export" : undefined,
  basePath: "/console",
  trailingSlash: true,
  assetPrefix: isProduction ? "/console" : undefined,
  devIndicators: false,
  turbopack: {
    root: __dirname,
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;