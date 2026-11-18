# The frontend as a static site: a node stage builds dist/, an nginx stage serves it and forwards
# /api and /static to the api (see nginx.conf). Nothing of node reaches the final image.

# --- build stage ---
# pinned exactly, like the backend's python: a moving tag would make a rebuild months later differ
FROM node:22.19.0-alpine AS builder

WORKDIR /app

# dependencies first, on their own: this layer only rebuilds when package.json or the lockfile change.
# npm ci installs exactly what package-lock.json says and fails if it disagrees with package.json
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# then the code. `npm run build` type checks (tsc -b) before vite builds, so a type error fails the image
COPY . ./
RUN npm run build

# --- final stage ---
# the unprivileged nginx runs as a non-root user and listens on 8080 (a non-root process can't bind 80)
FROM nginxinc/nginx-unprivileged:1.29.1-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080
