# syntax=docker/dockerfile:1.7
# Build context: ./mt-pricing-frontend (Next.js compilado previamente en CI runner)
# Docker solo empaqueta el standalone output — no hay build aquí.

FROM node:26-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN apt-get update && apt-get install -y --no-install-recommends wget \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd --system --gid 1001 nodejs \
  && useradd --system --uid 1001 nextjs
COPY --chown=nextjs:nodejs .next/standalone ./
# En monorepo pnpm, standalone genera mt-pricing-frontend/server.js, no server.js en raíz.
# Static y public van dentro del subdir del paquete para que el servidor los encuentre.
COPY --chown=nextjs:nodejs .next/static ./mt-pricing-frontend/.next/static
COPY --chown=nextjs:nodejs public ./mt-pricing-frontend/public
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD wget -qO- http://localhost:3000/api/health || exit 1
CMD ["node", "mt-pricing-frontend/server.js"]
