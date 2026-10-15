FROM node:24.22.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM caddy:2.11.7-alpine
COPY --from=build /app/build /srv
# shortcut: plain static server on :8080; security headers and HTTPS come with the prod Caddyfile (step 7)
USER 10001
EXPOSE 8080
CMD ["caddy", "file-server", "--root", "/srv", "--listen", ":8080"]
