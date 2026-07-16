# Build Stage
FROM node:20-alpine AS build

WORKDIR /app

# Copy package configurations
COPY package*.json ./

# Install packages
RUN npm install

# Copy frontend source files
COPY . .

# Receive the API base URL argument at build time (defaults to local backend if not specified)
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build the static distribution files
RUN npm run build

# Serving Stage
FROM nginx:alpine

# Copy built assets from build stage to nginx serving directory
COPY --from=build /app/dist /usr/share/nginx/html

# Copy our custom Nginx config for routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose Nginx server port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
