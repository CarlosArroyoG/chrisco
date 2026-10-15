# Web de CHRISCO Go: compila Angular y lo sirve con Caddy (HTTPS automático + proxy a /api).
# Construir desde la carpeta frontend/:  docker build -t chrisco-web .
FROM node:24-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npx ng build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist/frontend/browser /srv
