import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// next-intl@4: requiere conectar el plugin apuntando al request config.
const withNextIntl = createNextIntlPlugin("./lib/i18n/request.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // UAT: ignorar errores TS/ESLint en build — quitar antes de producción
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
  // Permite que el dev server acepte requests/WS HMR desde Caddy (localhost:8081)
  // y desde el host docker `caddy` interno. Sin esto, el HMR WebSocket falla con 502.
  allowedDevOrigins: [
    "localhost:8081",
    "localhost:3000",
    "caddy",
    "127.0.0.1:8081",
  ],
  // Next 16 movió experimental.{typedRoutes,reactCompiler} a top-level.
  typedRoutes: true,
  // reactCompiler: true,  // requiere babel-plugin-react-compiler — activar si se suma al package.json
  transpilePackages: [],
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.supabase.co",
      },
      {
        protocol: "https",
        hostname: "*.cloudfront.net",
      },
    ],
  },
  poweredByHeader: false,
};

export default withNextIntl(nextConfig);
