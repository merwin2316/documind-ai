import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Optimize package imports to reduce bundle size and improve tree-shaking
  experimental: {
    optimizePackageImports: [
      'lucide-react',
      'framer-motion',
      '@radix-ui/react-dialog',
      '@radix-ui/react-label',
      '@radix-ui/react-slot',
      'react-markdown',
    ],
  },

  // Silence the workspace root warning
  outputFileTracingRoot: undefined,

  // Explicitly enable Turbopack (default in Next.js 16)
  // Empty config acknowledges we're using Turbopack with minimal webpack config
  turbopack: {},

  // Only use webpack config when absolutely necessary (for PDF viewer compatibility)
  webpack: (config, { isServer }) => {
    // Client-side configuration - minimal changes for PDF viewer
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        canvas: false,
        fs: false,
      };
    }

    // Server-side configuration - externalize PDF libraries
    if (isServer) {
      config.externals = config.externals || [];
      config.externals.push(({ request }: any, callback: any) => {
        if (request?.includes('@react-pdf-viewer') || request === 'pdfjs-dist') {
          return callback(null, `commonjs ${request}`);
        }
        callback();
      });
    }

    return config;
  },

  // Docker Optimization: Standalone build for smaller images
  output: "standalone",
};

export default nextConfig;
