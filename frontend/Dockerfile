# Stage 1: Build the React Application
FROM node:18-alpine AS build

# Set the working directory in the container
WORKDIR /app

# Copy the package.json and package-lock.json into the container
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Build the application for production
RUN npm run build

# Stage 2: Serve the React Application using Nginx
FROM nginx:alpine

# Copy the build output from the build stage to the Nginx html directory
COPY --from=build /app/dist /usr/share/nginx/html

# Copy the custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 (to be mapped to 90)
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
