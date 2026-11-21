# syntax=docker/dockerfile:1
# web: the SPA built with Vite, served by unprivileged nginx that also proxies /api to api:8000.
# Build on Debian slim (glibc): the native TypeScript 7 compiler and Rollup ship prebuilt binaries.

ARG NODE_IMAGE=node:26.13.1-trixie-slim
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.30.6-alpine3.24-slim

# --- build: npm ci from package-lock.json, then tsc + vite build ----------------------------------
FROM ${NODE_IMAGE} AS build
WORKDIR /web
# Dependencies first, so that a code change does not invalidate this layer.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund
COPY . .
# Validator test vectors shared with pytest; tsc -b type-checks the tests that import them from
# ../fixtures (build with compose, which supplies this context).
COPY --from=fixtures validators.json /fixtures/validators.json
RUN npm run build

# --- runtime: static files + nginx ----------------------------------------------------------------
FROM ${NGINX_IMAGE} AS runtime

# Our nginx.conf does not include conf.d, so the stock default server is never loaded; removing
# it also keeps the image's entrypoint scripts from trying to rewrite it on a read-only root.
USER root
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf
# Owned by root, so the nginx user can read but not modify what it serves.
COPY --from=build /web/dist /usr/share/nginx/html
USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
