FROM node:20-alpine AS build

WORKDIR /app
COPY services/seller_ui/package*.json ./
RUN npm ci
COPY services/seller_ui ./
RUN npm run build

FROM nginx:1.27-alpine
COPY services/seller_ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
