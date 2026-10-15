# MindScan Frontend Production Dockerfile
FROM nginx:1.25-alpine

# Remove default Nginx welcome assets
RUN rm -rf /usr/share/nginx/html/*

# Copy custom production Nginx configuration with compression & reverse proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy static frontend web assets (HTML, CSS, JS)
COPY . /usr/share/nginx/html/

# Remove the nginx.conf from webroot if copied
RUN rm -f /usr/share/nginx/html/nginx.conf /usr/share/nginx/html/Dockerfile

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
