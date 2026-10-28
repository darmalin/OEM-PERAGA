# Production web image: builds the desk SPA, the scanner PWA (at /scanner/), and the public
# campaign form (at /r/, or on its own host), and serves them
# with nginx, which also proxies /api.
# Build from the repo root:  docker build -f frontend/Dockerfile .
FROM node:24-alpine AS build
WORKDIR /src/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
COPY frontend/apps/web/package.json apps/web/
COPY frontend/apps/scanner/package.json apps/scanner/
COPY frontend/apps/campaign/package.json apps/campaign/
COPY frontend/packages/api/package.json packages/api/
COPY frontend/packages/ui/package.json packages/ui/
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm --filter @ems/web --filter @ems/scanner --filter @ems/campaign build

FROM nginx:1.27-alpine
COPY deployments/nginx/default.conf /etc/nginx/conf.d/default.conf
# Campaign forms on their own host when EMS_CAMPAIGN_BASE_URL is set (FEATURES/12).
COPY deployments/nginx/campaign/ /etc/nginx/campaign/
COPY --chmod=755 deployments/nginx/campaign/15-campaign-host.sh /docker-entrypoint.d/
COPY --from=build /src/frontend/apps/web/dist /usr/share/nginx/html
COPY --from=build /src/frontend/apps/scanner/dist /usr/share/nginx/html/scanner
COPY --from=build /src/frontend/apps/campaign/dist /usr/share/nginx/html/r
