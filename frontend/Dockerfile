# syntax=docker/dockerfile:1.6
ARG NODE_VERSION=20
ARG NGINX_VERSION=1.27

###########################
# Build stage
###########################
FROM node:${NODE_VERSION}-alpine AS build
WORKDIR /app

ARG VITE_API_BASE_URL=http://localhost:8080
ARG NPM_CONFIG_REGISTRY=https://registry.npmjs.org/
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY}

COPY .npmrc package*.json ./

RUN --mount=type=cache,target=/root/.npm \
    npm ci --ignore-scripts && \
    npm cache verify

COPY . .
RUN --mount=type=cache,target=/root/.npm \
    npm run build

###########################
# Runtime stage
###########################
FROM nginx:${NGINX_VERSION}-alpine AS runtime
ENV NGINX_ENTRYPOINT_QUIET_LOGS=1

COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
