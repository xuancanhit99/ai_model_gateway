# ---- Stage 1: Build ----
# Use an official Node runtime as a parent image
FROM node:20-slim AS build

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install -g typescript
RUN npm install

# Copy the rest of the application code
COPY . .

# Install Vite globally to avoid permission issues
RUN npm install -g vite

# Make node_modules binaries executable
RUN chmod -R 755 /app/node_modules/.bin/

# Define ARGs for Supabase environment variables
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY

# Build the React app for production
# Run TypeScript compiler first, then use the global vite
RUN npx tsc -b && vite build

# ---- Stage 2: Serve ----
FROM nginx:stable-alpine

# Copy the build output from the build stage to Nginx's web root directory
COPY --from=build /app/dist /usr/share/nginx/html

# Copy a custom Nginx configuration file
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Command to run Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]