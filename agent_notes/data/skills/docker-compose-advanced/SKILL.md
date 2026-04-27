---
name: docker-compose-advanced
description: "Docker Compose advanced: database services, caches, proxies, dev/prod configs, and full stack examples"
group: docker
---

# Docker Compose (Advanced)

## Database Services

### PostgreSQL

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME:-myapp}
      # Performance tuning
      POSTGRES_SHARED_BUFFERS: 256MB
      POSTGRES_EFFECTIVE_CACHE_SIZE: 1GB
    volumes:
      # Data persistence
      - postgres_data:/var/lib/postgresql/data
      # Initialization scripts
      - ./db/init:/docker-entrypoint-initdb.d:ro
      # Backups
      - ./backups:/backups
    # SECURITY: Only expose in development, not production
    # ports:
    #   - "${DB_PORT:-5432}:5432"
    networks:
      - app_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

volumes:
  postgres_data:
    driver: local
```

### MySQL

```yaml
services:
  db:
    image: mysql:8.0
    restart: unless-stopped
    command: --default-authentication-plugin=mysql_native_password
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: ${DB_NAME:-myapp}
      MYSQL_USER: ${DB_USER:-myapp}
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
      - ./db/init:/docker-entrypoint-initdb.d:ro
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  mysql_data:
    driver: local
```

### MongoDB

```yaml
services:
  mongodb:
    image: mongo:7
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_USER:-admin}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}
      MONGO_INITDB_DATABASE: ${MONGO_DB:-myapp}
    volumes:
      - mongodb_data:/data/db
      - mongodb_config:/data/configdb
      - ./mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
    networks:
      - app_network
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet
      interval: 10s
      timeout: 10s
      retries: 5

volumes:
  mongodb_data:
    driver: local
  mongodb_config:
    driver: local
```

---

## Cache and Message Queue Services

### Redis

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf:ro
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512M

volumes:
  redis_data:
    driver: local
```

### RabbitMQ

```yaml
services:
  rabbitmq:
    image: rabbitmq:3-management-alpine
    restart: unless-stopped
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-admin}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: ${RABBITMQ_VHOST:-/}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    ports:
      - "5672:5672"      # AMQP
      - "15672:15672"    # Management UI
    networks:
      - app_network
    healthcheck:
      test: rabbitmq-diagnostics -q ping
      interval: 30s
      timeout: 10s
      retries: 5

volumes:
  rabbitmq_data:
    driver: local
```

---

## Reverse Proxy

### Nginx

```yaml
services:
  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      # Configuration
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      # Static files
      - ./public:/usr/share/nginx/html:ro
      # SSL certificates
      - ./certs:/etc/nginx/certs:ro
      # Logs
      - nginx_logs:/var/log/nginx
    depends_on:
      - app
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  nginx_logs:
    driver: local
```

### Traefik

```yaml
services:
  traefik:
    image: traefik:v2.10
    restart: unless-stopped
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=admin@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    networks:
      - app_network

  app:
    build: .
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.app.rule=Host(`example.com`)"
      - "traefik.http.routers.app.entrypoints=websecure"
      - "traefik.http.routers.app.tls.certresolver=letsencrypt"
    networks:
      - app_network
```

---

## Development vs Production

### Development Configuration

```yaml
# compose.dev.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    volumes:
      # Mount source code for hot reload
      - ./src:/app/src
      - ./public:/app/public
      # Don't mount node_modules (use container's version)
      - /app/node_modules
    ports:
      # Expose debugger port
      - "9229:9229"
    environment:
      - NODE_ENV=development
      - DEBUG=app:*
    command: npm run dev

  db:
    ports:
      # Expose database port for local access in development
      - "5432:5432"

# Usage: docker compose -f compose.yml -f compose.dev.yml up
```

### Production Configuration

```yaml
# compose.prod.yml
services:
  app:
    build:
      target: production
    restart: always
    # Don't expose ports directly in production - use reverse proxy
    expose:
      - "3000"
    environment:
      - NODE_ENV=production
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  db:
    # Don't expose database port in production
    expose:
      - "5432"
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

# Usage: docker compose -f compose.yml -f compose.prod.yml up -d
```

---

## Environment Variables

### .env File

```bash
# .env
NODE_ENV=production
APP_PORT=3000

# Database
DB_USER=postgres
DB_PASSWORD=secure_password_here
DB_NAME=myapp
DB_PORT=5432

# Redis
REDIS_PASSWORD=redis_password_here

# Application
JWT_SECRET=your_jwt_secret_here
API_KEY=your_api_key_here

# Version
VERSION=1.0.0
```

### Using Environment Variables

```yaml
services:
  app:
    image: ${APP_NAME:-myapp}:${VERSION:-latest}
    ports:
      - "${APP_PORT:-3000}:3000"
    environment:
      # Use variables from .env
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:${DB_PORT}/${DB_NAME}
      - API_KEY=${API_KEY}
    env_file:
      # Load all variables from .env
      - .env
```

---

## Full Stack Application Example

```yaml
services:
  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: production
    image: myapp-frontend:latest
    restart: unless-stopped
    depends_on:
      - backend
    networks:
      - app_network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`myapp.com`)"

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    image: myapp-backend:latest
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/myapp
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - uploads:/app/uploads
    networks:
      - app_network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`api.myapp.com`)"

  # Background Worker
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: npm run worker
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    networks:
      - app_network

  # Database
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=myapp
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Cache
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Reverse Proxy
  traefik:
    image: traefik:v2.10
    restart: unless-stopped
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - app_network

volumes:
  postgres_data:
  redis_data:
  uploads:

networks:
  app_network:
    driver: bridge
```

---

## Best Practices

### ✅ DO

1. **Remove version field** - It's obsolete in Compose v2
2. **Use health checks** - Essential for orchestration
3. **Use named volumes** - Data persistence
4. **Set resource limits** - Prevent resource exhaustion
5. **Use restart policies** - Automatic recovery
6. **Isolate with networks** - Security
7. **Pin image versions** - Use specific tags, not :latest
8. **Use .env files** - Centralized configuration
9. **Separate dev/prod configs** - Different requirements
10. **Use depends_on conditions** - Proper startup order

### ❌ DON'T

1. **Include version field** - Generates warnings in Compose v2
2. **Use :latest in production** - Unpredictable
3. **Expose database ports** - Security risk in production
4. **Hardcode secrets** - Use environment variables
5. **Use privileged mode** - Security risk
6. **Mount sensitive host directories** - Security risk
7. **Forget resource limits** - Can exhaust host
8. **Use bridge network for everything** - Proper isolation matters

---

## Common Commands

```bash
# Start services
docker compose up -d

# Start with specific file
docker compose -f compose.yml -f compose.prod.yml up -d

# View logs
docker compose logs -f app

# Restart service
docker compose restart app

# Stop services
docker compose down

# Stop and remove volumes (CAUTION: deletes data)
docker compose down -v

# Build and start
docker compose up --build

# Scale service
docker compose up -d --scale worker=3

# Execute command in running container
docker compose exec app sh

# Run one-off command
docker compose run --rm app npm test

# View service status
docker compose ps

# View resource usage
docker compose stats
```

---

## References and Sources

This guide is based on official Docker Compose documentation:

- [Docker Compose Specification](https://docs.docker.com/reference/compose-file/)
- [Docker Compose Services Reference](https://docs.docker.com/reference/compose-file/services/)
- [Docker Compose Health Checks](https://docs.docker.com/reference/compose-file/services/#healthcheck)
- [Docker Compose depends_on](https://docs.docker.com/reference/compose-file/services/#depends_on)
- [Docker Compose Legacy Versions](https://docs.docker.com/reference/compose-file/legacy-versions/)

Last updated: December 2025
