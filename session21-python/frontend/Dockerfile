FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
# bumped from nginx:1.27-alpine (alpine 3.21, 44 HIGH/CRITICAL in Trivy) and OS packages upgraded
FROM nginx:1.29-alpine
RUN apk upgrade --no-cache
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
