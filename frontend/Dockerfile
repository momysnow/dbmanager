# Production multi-stage build for the DBManager frontend.
# Build the static bundle in a node image, then serve it with nginx.
# For local development with hot-reload, use Dockerfile.dev (bind-mount + vite dev server).

FROM node:26-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --legacy-peer-deps --no-audit --no-fund

COPY . .

RUN npm run build


FROM nginx:1.27-alpine AS runtime

# nginx:alpine ships an `nginx` user (uid 101). We keep nginx as PID 1 (it
# drops to that user for workers itself) but make all served files owned by
# it so the read path needs no extra permission grants.
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Prepare writable tmp dirs for nginx so the container can run with a
# read-only root filesystem if the operator opts in via compose.
RUN install -d -o nginx -g nginx \
    /var/cache/nginx /var/run/nginx /var/log/nginx \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

EXPOSE 5173

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:5173/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
