FROM nginx:alpine

RUN apk add --no-cache bash

RUN mkdir -p /var/cache/nginx/proxy_cache

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
