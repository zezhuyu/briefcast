/** @type {import('next').NextConfig} */
import dotenv from "dotenv";

dotenv.config();

const nextConfig = {
  typescript: {
    // !! WARN !!
    // Dangerously allow production builds to successfully complete even if
    // your project has type errors.
    // !! WARN !!
    ignoreBuildErrors: true,
  },
  images: {
    domains: ['your-backend.com'],
    loader: 'custom',
    loaderFile: './src/utils/imageLoader.js',
  },
  async rewrites() {
    return [
      {
        source: '/media/:path*',
        destination: 'https://your-backend.com/:path*',
      },
    ];
  },
};

export default nextConfig;