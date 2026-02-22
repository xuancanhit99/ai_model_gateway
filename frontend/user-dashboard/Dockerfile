# ---- Stage 1: Build ----
# Use an official Node runtime as a parent image
FROM node:20-slim AS build

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
# No global installs needed, use local versions via npm scripts or npx
RUN npm install

# Copy the rest of the application code
# Ensure binaries installed by npm have execute permissions
RUN chmod -R 755 /app/node_modules/.bin/
COPY . .

# Define ARGs for IDSafe environment variables
ARG VITE_IDSAFE_URL
ARG VITE_IDSAFE_REALM
ARG VITE_IDSAFE_CLIENT_ID

ENV VITE_IDSAFE_URL=${VITE_IDSAFE_URL}
ENV VITE_IDSAFE_REALM=${VITE_IDSAFE_REALM}
ENV VITE_IDSAFE_CLIENT_ID=${VITE_IDSAFE_CLIENT_ID}

# Build the React app for production by directly invoking tsc and vite scripts with node
# This bypasses potential issues with npx or script execution permissions
RUN node ./node_modules/typescript/bin/tsc -b && node ./node_modules/vite/bin/vite.js build

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
