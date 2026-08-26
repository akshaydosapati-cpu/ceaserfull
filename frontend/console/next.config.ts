import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/console",
  trailingSlash: true,
  assetPrefix: "/console",
  devIndicators: false,
  turbopack: {
    root: __dirname,
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
