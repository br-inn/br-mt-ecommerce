# syntax=docker/dockerfile:1.7
# Build context: REPO ROOT (context: .)
# Usa el pnpm-lock.yaml del monorepo para installs determinísticos.

FROM node:20-slim AS deps
WORKDIR /repo
RUN corepack enable && corepack prepare pnpm@9.0.0 --activate
# Copiar archivos del workspace para install determinístico
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY mt-pricing-frontend/package.json ./mt-pricing-frontend/
RUN pnpm install --frozen-lockfile --filter mt-pricing-frontend...

FROM node:20-slim AS builder
WORKDIR /repo
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN corepack enable && corepack prepare pnpm@9.0.0 --activate
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/mt-pricing-frontend/node_modules ./mt-pricing-frontend/node_modules
COPY mt-pricing-frontend/ ./mt-pricing-frontend/
WORKDIR /repo/mt-pricing-frontend
RUN pnpm build

FROM node:20-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN apt-get update && apt-get install -y --no-install-recommends wget \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd --system --gid 1001 nodejs \
  && useradd --system --uid 1001 nextjs
COPY --from=builder /repo/mt-pricing-frontend/public ./public
COPY --from=builder --chown=nextjs:nodejs /repo/mt-pricing-frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/mt-pricing-frontend/.next/static ./.next/static
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD wget -qO- http://localhost:3000/api/health || exit 1
CMD ["node", "server.js"]
