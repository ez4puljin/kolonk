# Build context is the repo root (see docker-compose nginx service).
FROM node:24-alpine AS build
WORKDIR /app
# lock файлыг хамт хуулж `npm ci` ашигласнаар build давтагдах чадвартай,
# мөн cache-д ээлтэй (эх код өөрчлөгдөхөд dependency дахин суухгүй).
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY infra/nginx/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
