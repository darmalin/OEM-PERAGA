# Production web image: builds the SPA and serves it with nginx, which also proxies /api.
# Build from the repo root:  docker build -f frontend/Dockerfile .
FROM node:24-alpine AS build
WORKDIR /src/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
COPY frontend/apps/web/package.json apps/web/
COPY frontend/packages/api/package.json packages/api/
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm --filter @ems/web build

FROM nginx:1.27-alpine
COPY deployments/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/frontend/apps/web/dist /usr/share/nginx/html
